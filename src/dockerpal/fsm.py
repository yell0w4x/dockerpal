import docker
from textual.containers import Grid
from textual.widgets import DataTable, Footer, Header, Input, Label, Button, TextArea, ListView, ListItem
from textual import events
from textual.screen import Screen, ModalScreen
from textual._context import active_app
from textual.containers import Horizontal
from textual.binding import Binding
from textual.css.query import NoMatches
from time import monotonic
from rich.text import Text
from rich.style import Style

import json
import re

from pathlib import Path

from dockerpal import clipboard


SIDEBAR_ITEMS = ('images', 'containers', 'networks', 'volumes')


def split_image_name(name):
    """Split 'repo:tag' into its parts, leaving a registry port alone."""
    repository, sep, tag = name.rpartition(':')
    if not sep or '/' in tag:
        return name, 'latest'
    return repository, tag


def compose_sidebar(current=None):
    """Yield the sidebar list, highlighting ``current`` (e.g. 'containers')."""
    index = SIDEBAR_ITEMS.index(current) if current in SIDEBAR_ITEMS else 0
    with ListView(id='sidebar', initial_index=index):
        for name in SIDEBAR_ITEMS:
            yield ListItem(Label(name.capitalize()), id=f'{name}-sidebar-item')


class ScreenStateBase:
    def __init__(self, ctx):
        super().__init__()
        self.__ctx = ctx

    def on_state_key(self, event: events.Key):
        pass

    def on_state_enter(self, data=None):
        pass

    def on_state_exit(self):
        pass

    def focus_main(self):
        """Give focus back to the screen's main widget (after the sidebar hides)."""
        pass

    def context(self):
        return self.__ctx


class ScreenFSM:
    SIDEBAR_ITEMS = {
        'images-sidebar-item': 'set_images_screen',
        'containers-sidebar-item': 'set_containers_screen',
        'networks-sidebar-item': 'set_networks_screen',
        'volumes-sidebar-item': 'set_volumes_screen',
    }

    def __init__(self, docker_cli):
        self.__state = None
        self.__docker_cli = docker_cli
        self.__rows = dict()


    def set_images_screen(self):
        self.set_state(ImagesScreen(self, self.__docker_cli))


    def set_containers_screen(self):
        self.set_state(ContainersScreen(self, self.__docker_cli))


    def set_networks_screen(self):
        self.set_state(NetworksScreen(self, self.__docker_cli))


    def set_volumes_screen(self):
        self.set_state(VolumesScreen(self, self.__docker_cli))


    def remember_row(self, screen_id, row):
        self.__rows[screen_id] = row


    def remembered_row(self, screen_id):
        return self.__rows.get(screen_id)


    def activate_sidebar_item(self):
        sidebar = self.__app().get_child_by_id('sidebar')
        item = sidebar.highlighted_child
        if item is None:
            return
        target = item.id.removesuffix('-sidebar-item')
        if self.__state.id == f'{target}-screen':
            # Already there: a fresh screen with the same id can't be mounted.
            self.hide_sidebar()
            return
        getattr(self, self.SIDEBAR_ITEMS[item.id])()


    def set_details_screen(self, item, title, back, name):
        """Show ``item.attrs`` as JSON; ``back`` is the FSM method name to
        call on Escape, ``name`` the basename used when exporting."""
        self.set_state(DetailsScreen(self, item, title, back, name))


    def set_state(self, state, data=None):
        if self.__state is not None:
            self.__state.on_state_exit()
        self.__state = state
        self.__state.on_state_enter(data)


    def state(self):
        return self.__state
    

    def compose(self):
        return self.__state.compose()


    def on_state_key(self, event: events.Key):
        try:
            self.__state.on_state_key(event)
        except NoMatches:
            # Workaround when textual tray is open
            pass
        except Exception as e:
            self.notify(str(e), severity='error')


    def set_subtitle(self, subtitle):
        self.__app().sub_title = subtitle


    def switch_screen(self, screen):
        self.__app().switch_screen(screen)
    

    def notify(self, message, severity='information'):
        self.__app().notify(message, severity=severity)


    def toggle_sidebar(self):
        if self.is_sidebar_visible():
            self.hide_sidebar()
        else:
            self.show_sidebar()

        return self.is_sidebar_visible()


    def show_sidebar(self):
        sidebar = self.__app().get_child_by_id('sidebar')
        sidebar.styles.display = 'block'
        if sidebar.can_focus:
            sidebar.focus()


    def hide_sidebar(self):
        sidebar = self.__app().get_child_by_id('sidebar')
        sidebar.styles.display = 'none'
        self.__state.focus_main()


    def is_sidebar_visible(self):
        app = self.__app()
        sidebar = app.get_child_by_id('sidebar')
        return sidebar.styles.display != 'none'


    def exit(self):
        self.__app().exit()


    def app(self):
        return self.__app()


    def __app(self):
        return active_app.get()


class SearchInput(Input):
    """Search box: Escape abandons the search, Enter keeps the filter."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def action_cancel(self):
        self.screen.cancel_search()


class ResourceScreen(Screen, ScreenStateBase):
    """Base for list screens: a DataTable with multi-row selection, a footer with
    totals, sidebar navigation and vi-like movement keys.

    Subclasses define SCREEN_ID, HEADING, COLUMNS and the docker accessors."""

    SCREEN_ID = None
    HEADING = None
    ITEM_NAME = 'item'
    COLUMNS = ()
    # (label, action name, key hint) offered by the actions menu; 'foo' runs action_foo.
    ACTIONS = (
        ('Remove', 'delete', 'd'),
        ('Details', 'details', 'enter'),
    )
    SELECTED_SYMBOL = '[✓]'

    BINDINGS = [
        Binding("d,delete", "delete", "Remove"),
        Binding("r", "refresh", "Refresh"),
        Binding("space", "select_row", "Select row"),
        Binding("+", "select_all", "Select all"),
        Binding("-", "deselect_all", "Deselect all"),
        Binding("*", "invert_selection", "Invert selection"),
        Binding("a", "actions", "Actions"),
        Binding("slash", "search", "Search"),
        Binding("s", "sidebar", "Sidebar"),
        Binding("q,escape", "exit", "Exit"),
        Binding("j", "down", "Down", show=False),
        Binding("k", "up", "Up", show=False),
        Binding("f", "page_down", "Page down", show=False),
        Binding("b", "page_up", "Page up", show=False),
        Binding("g", "go_up", "Go up (double press)", show=False),
        Binding("G", "go_down", "Go down", show=False),
    ]

    def __init__(self, ctx, docker_cli):
        Screen.__init__(self, id=self.SCREEN_ID)
        ScreenStateBase.__init__(self, ctx)
        self._cli = docker_cli
        table = DataTable(id=self.table_id(), cursor_type='row', zebra_stripes=False)
        for column in self.COLUMNS:
            table.add_column(column)
        self.__double_press = dict()
        self._table = table
        self.__num_space_pad = 0
        self.__selected = set()
        self.__total_label = Label()
        self.__selected_label = Label()
        self.__search = SearchInput(placeholder=f'Search {self.ITEM_NAME}s...', id='search')
        self.__search.display = False
        self.__search_prompt = Label('/', id='search-prompt')
        self.__search_prompt.display = False
        self.__query = ''
        self.__query_before_search = ''
        self.renew()

    # --- to be provided by subclasses -------------------------------------

    def list_items(self):
        raise NotImplementedError

    def item_key(self, item):
        raise NotImplementedError

    def item_row(self, item):
        raise NotImplementedError

    def get_item(self, key):
        raise NotImplementedError

    def remove_item(self, key, force=False):
        raise NotImplementedError

    def open_details(self, item):
        raise NotImplementedError

    # ---------------------------------------------------------------------

    @classmethod
    def table_id(cls):
        return f'{cls.SCREEN_ID.removesuffix("-screen")}-table'

    def renew(self):
        items = self.list_items()
        rows = [(self.item_key(item), self.item_row(item)) for item in items]
        shown = [(key, row) for key, row in rows if self.__matches(row)]
        # Items that are gone (deleted elsewhere, say) leave the selection.
        self.__selected &= {key for key, _ in rows}

        table = self._table
        table.clear()
        self.__num_space_pad = len(str(len(shown))) + len(self.SELECTED_SYMBOL) + 2
        for i, (key, row) in enumerate(shown, 1):
            table.add_row(*row, key=key, label=self.__row_label(i, key in self.__selected))
        self.__update_footer(len(shown), len(rows))

    def __matches(self, row):
        if not self.__query:
            return True
        query = self.__query.lower()
        return any(query in str(cell).lower() for cell in row)

    def compose(self):
        yield from compose_sidebar(self.SCREEN_ID.removesuffix('-screen'))
        yield Header()
        yield self._table
        with Horizontal(id="table-footer"):
            yield self.__total_label
            yield self.__selected_label
            yield self.__search_prompt
            yield self.__search
        yield Footer()

    def on_state_enter(self, data=None):
        context = self.context()
        context.set_subtitle(self.HEADING)
        context.switch_screen(self)
        row = context.remembered_row(self.SCREEN_ID)
        if row is not None:
            self.__set_cursor_row(row)

    def on_state_exit(self):
        self.context().remember_row(self.SCREEN_ID, self._table.cursor_row)

    def on_state_key(self, event: events.Key):
        context = self.context()
        match event.key:
            case 'escape':
                if context.is_sidebar_visible():
                    context.hide_sidebar()
                elif self.has_filter():
                    self.clear_search()
                else:
                    context.exit()
            case 'enter':
                if context.is_sidebar_visible():
                    context.activate_sidebar_item()
                else:
                    self.action_details()

    def action_select_all(self):
        """Select every visible row (rows hidden by a search keep their state)."""
        self.__set_visible_selection(lambda selected: True)

    def action_deselect_all(self):
        self.__set_visible_selection(lambda selected: False)

    def action_invert_selection(self):
        self.__set_visible_selection(lambda selected: not selected)

    def action_select_row(self):
        if self._table.row_count == 0:
            return
        self.__toggle_row_sel()
        self.__update_selected_label()

    def action_down(self):
        self._table.action_cursor_down()

    def action_up(self):
        self._table.action_cursor_up()

    def action_page_down(self):
        self._table.action_page_down()

    def action_page_up(self):
        self._table.action_page_up()

    def action_go_up(self):
        table = self._table
        dp = self.__double_press
        before = dp.get('g')
        if before is None:
            dp['g'] = monotonic()
            return

        now = monotonic()
        if now - dp.get('g') < 0.2:
            table.action_scroll_top()
            dp.pop('g', None)
            return

        dp['g'] = now

    def action_go_down(self):
        self._table.action_scroll_bottom()

    def action_delete(self):
        self.__confirm_remove('Remove', force=False)

    def action_force_delete(self):
        self.__confirm_remove('Force remove', force=True)

    def action_details(self):
        item = self.cursor_item()
        if item is not None:
            self.open_details(item)

    def cursor_item(self):
        """The item under the cursor, or None when the table is empty."""
        if self._table.row_count == 0:
            return None
        return self.__get_row_item(self._table.cursor_row)

    def action_actions(self):
        """Show the actions menu for the current selection."""
        count = self.__selection_size()
        if count == 0:
            return

        def on_choice(name):
            if name is not None:
                getattr(self, f'action_{name}')()
            else:
                self.focus_main()

        self.app.push_screen(ActionsMenu(f'Actions: {self.__count_phrase(count)}', self.ACTIONS), on_choice)

    def __count_phrase(self, count):
        noun = self.ITEM_NAME if count == 1 else f'{self.ITEM_NAME}s'
        return f'{count} {noun}'

    def __confirm_remove(self, verb, force):
        count = self.__selection_size()
        if count == 0:
            return

        def on_answer(confirmed):
            if confirmed:
                self.apply_to_selection(lambda key: self.remove_item(key, force=force))
            self.focus_main()

        self.app.push_screen(ConfirmScreen(f'{verb} {self.__count_phrase(count)}?'), on_answer)

    def apply_to_selection(self, func):
        """Run ``func(key)`` on the selected items, or on the cursor row when
        nothing is selected, then reload the table."""
        targets = self.__selection_keys()
        if not targets:
            return

        cursor_row = self._table.cursor_row
        try:
            for key in targets:
                func(key)
        except docker.errors.APIError as e:
            self.context().notify(e.explanation or str(e), severity='error')
        finally:
            self.renew()
            self.__set_cursor_row(cursor_row)

    def action_refresh(self):
        self.renew()

    def action_sidebar(self):
        self.context().toggle_sidebar()

    def action_search(self):
        search = self.__search
        self.__query_before_search = self.__query
        search.display = True
        search.value = self.__query
        self.__update_search_prompt(editing=True)
        search.focus()

    def cancel_search(self):
        """Close the search box, going back to the filter it was opened with."""
        if self.__query != self.__query_before_search:
            self.__query = self.__query_before_search
            self.renew()
        self.__close_search()

    def clear_search(self):
        """Drop the active filter and show every row again."""
        self.__query = ''
        self.renew()
        self.__close_search()

    def has_filter(self):
        return bool(self.__query)

    def on_input_changed(self, event: Input.Changed):
        if event.input is self.__search:
            self.__query = event.value
            self.renew()

    def on_input_submitted(self, event: Input.Submitted):
        if event.input is self.__search:
            self.__close_search()

    def is_searching(self):
        return self.__search.display

    def __close_search(self):
        self.__search.display = False
        self.__update_search_prompt(editing=False)
        self.focus_main()

    def __update_search_prompt(self, editing):
        """While editing show a bare '/'; afterwards keep '/query' as a
        reminder that rows are hidden (Escape clears it)."""
        prompt = self.__search_prompt
        prompt.display = editing or self.has_filter()
        prompt.update('/' if editing else f'/{self.__query}')

    def on_mount(self):
        self.focus_main()

    def focus_main(self):
        self._table.focus()

    def __set_cursor_row(self, row_index):
        table = self._table
        if table.row_count > row_index:
            table.move_cursor(row=row_index)
        elif table.row_count > 0:
            table.move_cursor(row=table.row_count - 1)

    def __update_footer(self, shown, total):
        text = f'Total: {shown}/{total}' if self.__query else f'Total: {total}'
        self.__total_label.update(text)
        self.__update_selected_label()

    def __update_selected_label(self):
        self.__selected_label.update(f'Selected: {len(self.__selected)}')

    def __toggle_row_sel(self, cursor_row=None, move_cursor=True):
        if cursor_row is None:
            cursor_row = self._table.cursor_row

        table = self._table
        rows = tuple(table.rows.items())
        row_key, row = rows[cursor_row]
        col_key, _ = next(iter(table.columns.items()))

        selected = self.__selected
        key = row_key.value
        if key in selected:
            selected.remove(key)
        else:
            selected.add(key)
        row.label = self.__row_label(cursor_row + 1, key in selected)

        # Updating a cell is what makes the table redraw the row label.
        cell_val = table.get_cell(row_key, col_key)
        table.update_cell(row_key, col_key, cell_val, update_width=True)
        if move_cursor:
            table.action_cursor_down()

    def __selection_keys(self):
        """The selected item keys, or the cursor row when nothing is selected."""
        if self.__selected:
            return sorted(self.__selected)
        if self._table.row_count == 0:
            return []
        return [self.__get_row_key(self._table.cursor_row)]

    def __selection_size(self):
        return len(self.__selection_keys())

    def __set_visible_selection(self, decide):
        """Apply ``decide(is_selected)`` to every visible row."""
        for i in range(self._table.row_count):
            key = self.__get_row_key(i)
            if decide(key in self.__selected) != (key in self.__selected):
                self.__toggle_row_sel(i, move_cursor=False)
        self.__update_selected_label()

    def __row_label(self, index, selected):
        pad = self.__num_space_pad
        if not selected:
            return Text(f'{index: <{pad}}')
        label = Text(f'{index: <{len(self.SELECTED_SYMBOL)}}', style=Style(color='#FA8072'))
        label.append(self.SELECTED_SYMBOL)
        return label

    def __get_row_key(self, row_index):
        rows = tuple(self._table.rows.items())
        row_key, _ = rows[row_index]
        return row_key.value

    def __get_row_item(self, row_index):
        return self.get_item(self.__get_row_key(row_index))


class ImagesScreen(ResourceScreen):
    SCREEN_ID = 'images-screen'
    HEADING = 'Images'
    ITEM_NAME = 'image'
    COLUMNS = ('Short ID', 'Tags')
    ACTIONS = (
        ('Remove', 'delete', 'd'),
        ('Force remove', 'force_delete', ''),
        ('Details', 'details', 'enter'),
    )

    def list_items(self):
        return self._cli.images.list()

    def item_key(self, image):
        return image.id.split(':')[1]

    def item_row(self, image):
        short_id = image.short_id.split(':')[1]
        tags = ', '.join(image.tags) if image.tags else '<None>'
        return short_id, tags

    def get_item(self, key):
        return self._cli.images.get(key)

    def remove_item(self, key, force=False):
        self._cli.images.remove(key, force=force)

    def open_details(self, image):
        name = image.tags[0] if image.tags else image.short_id.split(':')[-1]
        self.context().set_details_screen(image, 'Image details', 'set_images_screen', name)


class ContainersScreen(ResourceScreen):
    SCREEN_ID = 'containers-screen'
    HEADING = 'Containers'
    ITEM_NAME = 'container'
    COLUMNS = ('Short ID', 'Name', 'Status', 'Image')
    ACTIONS = (
        ('Start', 'start', 'u'),
        ('Stop', 'stop', 'x'),
        ('Restart', 'restart', 't'),
        ('Commit as image', 'commit', 'c'),
        ('Remove', 'delete', 'd'),
        ('Force remove', 'force_delete', ''),
        ('Details', 'details', 'enter'),
    )

    BINDINGS = [
        Binding("u", "start", "Start"),
        Binding("x", "stop", "Stop"),
        Binding("t", "restart", "Restart"),
        Binding("c", "commit", "Commit"),
    ] + ResourceScreen.BINDINGS

    def action_start(self):
        self.apply_to_selection(lambda key: self.get_item(key).start())

    def action_stop(self):
        self.apply_to_selection(lambda key: self.get_item(key).stop())

    def action_restart(self):
        self.apply_to_selection(lambda key: self.get_item(key).restart())

    def action_commit(self):
        """Commit the container under the cursor as a new image.

        One image needs one name, so this works on the cursor row rather than
        the whole selection; the prompt says which container it is."""
        container = self.cursor_item()
        if container is None:
            return

        def on_name(name):
            if name:
                self.__commit(container, name)
            self.focus_main()

        self.app.push_screen(PromptScreen(f'Commit {container.name} as:',
                                          f'{container.name}:latest'), on_name)

    def __commit(self, container, name):
        repository, tag = split_image_name(name)
        try:
            image = container.commit(repository=repository, tag=tag)
        except docker.errors.APIError as e:
            self.context().notify(e.explanation or str(e), severity='error')
        else:
            short_id = image.short_id.split(':')[-1]
            self.context().notify(f'Committed {container.name} as {repository}:{tag} ({short_id})')

    def list_items(self):
        return self._cli.containers.list(all=True)

    def item_key(self, container):
        return container.id

    def item_row(self, container):
        # Like `docker ps`: the image name the container was created with.
        # (container.image would be an extra API call per row and fails if
        # the image has since been removed.)
        image_name = container.attrs.get('Config', {}).get('Image') or '<None>'
        return container.short_id, container.name, container.status, image_name

    def get_item(self, key):
        return self._cli.containers.get(key)

    def remove_item(self, key, force=False):
        self._cli.containers.get(key).remove(force=force)

    def open_details(self, container):
        self.context().set_details_screen(
            container, 'Container details', 'set_containers_screen', container.name)


class NetworksScreen(ResourceScreen):
    SCREEN_ID = 'networks-screen'
    HEADING = 'Networks'
    ITEM_NAME = 'network'
    COLUMNS = ('Short ID', 'Name', 'Driver', 'Scope')
    ACTIONS = (
        ('Remove', 'delete', 'd'),
        ('Details', 'details', 'enter'),
    )

    def list_items(self):
        return self._cli.networks.list()

    def item_key(self, network):
        return network.id

    def item_row(self, network):
        attrs = network.attrs
        return network.short_id, network.name, attrs.get('Driver', ''), attrs.get('Scope', '')

    def get_item(self, key):
        return self._cli.networks.get(key)

    def remove_item(self, key, force=False):
        # The docker API has no force flag for networks.
        self._cli.networks.get(key).remove()

    def open_details(self, network):
        self.context().set_details_screen(
            network, 'Network details', 'set_networks_screen', network.name)


class VolumesScreen(ResourceScreen):
    SCREEN_ID = 'volumes-screen'
    HEADING = 'Volumes'
    ITEM_NAME = 'volume'
    COLUMNS = ('Name', 'Driver', 'Mountpoint')
    ACTIONS = (
        ('Remove', 'delete', 'd'),
        ('Force remove', 'force_delete', ''),
        ('Details', 'details', 'enter'),
    )

    def list_items(self):
        return self._cli.volumes.list()

    def item_key(self, volume):
        return volume.name

    def item_row(self, volume):
        attrs = volume.attrs
        return volume.name, attrs.get('Driver', ''), attrs.get('Mountpoint', '')

    def get_item(self, key):
        return self._cli.volumes.get(key)

    def remove_item(self, key, force=False):
        self._cli.volumes.get(key).remove(force=force)

    def open_details(self, volume):
        self.context().set_details_screen(
            volume, 'Volume details', 'set_volumes_screen', volume.name)


class DetailsScreen(Screen, ScreenStateBase):
    BINDINGS = [
        Binding("escape", "exit", "Go back"),
        Binding("y", "copy", "Copy"),
        Binding("e", "export", "Export JSON"),
        Binding("s", "sidebar", "Sidebar"),
    ]

    def __init__(self, ctx, item, title, back, name):
        Screen.__init__(self, id='details-screen')
        ScreenStateBase.__init__(self, ctx)
        self.__item = item
        self.__title = title
        self.__back = back
        self.__name = name

    def action_exit(self):
        context = self.context()
        if context.is_sidebar_visible():
            context.hide_sidebar()
        else:
            getattr(context, self.__back)()

    def action_copy(self):
        """Copy the selection, or the whole document when nothing is selected."""
        details = self.get_child_by_id('details')
        text = details.selected_text or details.text
        lines = len(text.splitlines())
        plural = '' if lines == 1 else 's'

        tool = clipboard.copy(text)
        # Also emit OSC 52: that is what reaches the clipboard over ssh or tmux.
        self.app.copy_to_clipboard(text)

        if tool is None:
            self.context().notify(
                f'Copied {lines} line{plural} via terminal escape sequence only. '
                'Install xclip, xsel or wl-clipboard for reliable copying.',
                severity='warning')
        else:
            self.context().notify(f'Copied {lines} line{plural} to the clipboard ({tool})')

    def action_export(self):
        details = self.get_child_by_id('details')
        path = self.__export_path()
        try:
            path.write_text(details.text)
        except OSError as e:
            self.context().notify(f'Unable to export: {e}', severity='error')
        else:
            self.context().notify(f'Exported to {path}')

    def __export_path(self):
        """A free path in the current directory, so an export never clobbers."""
        stem = re.sub(r'[^A-Za-z0-9._-]', '_', self.__name) or 'details'
        path = Path(f'{stem}.json').resolve()
        i = 0
        while path.exists():
            i += 1
            path = Path(f'{stem}-{i}.json').resolve()
        return path

    def on_mount(self):
        self.focus_main()

    def focus_main(self):
        self.get_child_by_id('details').focus()

    def on_state_enter(self, data=None):
        self.context().set_subtitle(self.__title)
        self.context().switch_screen(self)

    def compose(self):
        yield from compose_sidebar(self.__back.removeprefix('set_').removesuffix('_screen'))
        yield Header()
        yield Footer()
        try:
            details = json.dumps(self.__item.attrs, indent=4)
        except (TypeError, ValueError) as e:
            yield TextArea(f'Unable to render details: {e}', read_only=True, id='details')
            self.context().notify(f'Unable to render details: {e}', severity='error')
        else:
            yield TextArea(details, read_only=True, language='json', id='details')

    def action_sidebar(self):
        self.context().toggle_sidebar()

    def on_state_key(self, event: events.Key):
        context = self.context()
        match event.key:
            case 'enter':
                if context.is_sidebar_visible():
                    context.activate_sidebar_item()
            case 'escape':
                self.action_exit()


class SplashScreen(Screen):
    def compose(self):
        yield Grid(Label("Initializing...", id='initializing-label'), id="splash-screen")


class ErrorScreen(Screen):
    BINDINGS = [
        Binding("q,escape", "exit", "Exit"),
    ]

    def __init__(self, message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__message = message

    def action_exit(self):
        self.app.exit()

    def compose(self):
        yield Grid(Label(self.__message, id='error-label'), id="error-screen")


class ActionsMenu(ModalScreen[str]):
    """Menu of the actions a screen offers for the current selection.

    Dismisses with the chosen action name, or None when cancelled."""

    BINDINGS = [
        Binding("escape,q", "cancel", "Cancel"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, title, actions):
        super().__init__(id='actions-menu')
        self.__title = title
        self.__actions = actions

    def compose(self):
        with Grid(id='actions-dialog'):
            yield Label(self.__title, id='actions-title')
            with ListView(id='actions-list'):
                for label, name, key in self.__actions:
                    yield ListItem(
                        Horizontal(
                            Label(label, classes='action-label'),
                            Label(key, classes='action-key'),
                        ),
                        id=f'action-{name}',
                    )

    def on_mount(self):
        self.query_one('#actions-list', ListView).focus()

    def action_cancel(self):
        self.dismiss(None)

    def action_cursor_down(self):
        self.query_one('#actions-list', ListView).action_cursor_down()

    def action_cursor_up(self):
        self.query_one('#actions-list', ListView).action_cursor_up()

    def on_list_view_selected(self, event: ListView.Selected):
        self.dismiss(event.item.id.removeprefix('action-'))


class PromptScreen(ModalScreen[str]):
    """Ask for a single line of text; dismisses with it, or None when cancelled."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title, value=''):
        super().__init__(id='prompt-screen')
        self.__title = title
        self.__value = value

    def compose(self):
        yield Grid(
            Label(self.__title, id='prompt-title'),
            Input(value=self.__value, id='prompt-input'),
            id='prompt-dialog',
        )

    def on_mount(self):
        self.query_one('#prompt-input', Input).focus()

    def action_cancel(self):
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted):
        self.dismiss(event.value.strip())


class ConfirmScreen(ModalScreen[bool]):
    """Yes/no dialog; dismisses with True on y/Enter/Yes, False on n/Escape/No."""

    BINDINGS = [
        Binding("y,enter", "yes", "Yes"),
        Binding("n,escape", "no", "No"),
    ]

    def __init__(self, question):
        super().__init__(id='confirm-screen')
        self.__question = question

    def compose(self):
        yield Grid(
            Label(self.__question, id="question"),
            Button("Yes", variant="error", id="yes"),
            Button("No", variant="primary", id="no"),
            id="dialog",
        )

    def on_mount(self):
        self.query_one('#no', Button).focus()

    def action_yes(self):
        self.dismiss(True)

    def action_no(self):
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == 'yes')
