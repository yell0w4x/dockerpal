import docker
from textual.containers import Grid
from textual.widgets import DataTable, Footer, Header, Label, Button, TextArea, ListView, ListItem
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


SIDEBAR_ITEMS = ('images', 'containers', 'networks', 'volumes')


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


    def set_details_screen(self, item, title, back):
        """Show ``item.attrs`` as JSON; ``back`` is the FSM method name to
        call on Escape."""
        self.set_state(DetailsScreen(self, item, title, back))


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


class ResourceScreen(Screen, ScreenStateBase):
    """Base for list screens: a DataTable with multi-row selection, a footer with
    totals, sidebar navigation and vi-like movement keys.

    Subclasses define SCREEN_ID, TITLE, COLUMNS and the docker accessors."""

    SCREEN_ID = None
    TITLE = None
    ITEM_NAME = 'item'
    COLUMNS = ()
    SELECTED_SYMBOL = '[✓]'

    BINDINGS = [
        Binding("d,delete", "delete", "Delete"),
        Binding("r", "refresh", "Refresh"),
        Binding("space", "select_row", "Select row"),
        Binding("+", "select_all", "Select all"),
        Binding("-", "deselect_all", "Deselect all"),
        Binding("*", "invert_selection", "Invert selection"),
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
        self.__selected_rows = set()
        self.__total_label = Label()
        self.__selected_label = Label()
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

    def remove_item(self, key):
        raise NotImplementedError

    def open_details(self, item):
        raise NotImplementedError

    # ---------------------------------------------------------------------

    @classmethod
    def table_id(cls):
        return f'{cls.SCREEN_ID.removesuffix("-screen")}-table'

    def renew(self):
        items = self.list_items()
        table = self._table
        table.clear()
        pad = self.__num_space_pad = len(str(len(items))) + len(self.SELECTED_SYMBOL) + 2
        for i, item in enumerate(items, 1):
            table.add_row(*self.item_row(item), key=self.item_key(item), label=f'{i: <{pad}}')
        self.__selected_rows.clear()
        self.__update_footer(len(items))

    def compose(self):
        yield from compose_sidebar(self.SCREEN_ID.removesuffix('-screen'))
        yield Header()
        yield self._table
        with Horizontal(id="table-footer"):
            yield self.__total_label
            yield self.__selected_label
        yield Footer()

    def on_state_enter(self, data=None):
        context = self.context()
        context.set_subtitle(self.TITLE)
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
                else:
                    context.exit()
            case 'enter':
                if context.is_sidebar_visible():
                    context.activate_sidebar_item()
                elif self._table.row_count > 0:
                    self.open_details(self.__get_row_item(self._table.cursor_row))

    def action_select_all(self):
        table = self._table
        sel_rows = self.__selected_rows
        sel_rows.clear()
        for i in range(len(table.rows)):
            self.__toggle_row_sel(i, move_cursor=False)
        self.__update_selected_label()

    def action_deselect_all(self):
        table = self._table
        self.__selected_rows = {i for i in range(len(table.rows))}
        for i in range(len(table.rows)):
            self.__toggle_row_sel(i, move_cursor=False)
        self.__update_selected_label()

    def action_invert_selection(self):
        table = self._table
        for i in range(len(table.rows)):
            self.__toggle_row_sel(i, move_cursor=False)
        self.__update_selected_label()

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
        count = self.__selection_size()
        if count == 0:
            return
        noun = self.ITEM_NAME if count == 1 else f'{self.ITEM_NAME}s'
        question = f'Delete {count} {noun}?'

        def on_answer(confirmed):
            if confirmed:
                self.apply_to_selection(self.remove_item)
            self.focus_main()

        self.app.push_screen(ConfirmScreen(question), on_answer)

    def apply_to_selection(self, func):
        """Run ``func(key)`` on the selected rows, or on the cursor row when
        nothing is selected, then reload the table."""
        table = self._table
        if table.row_count == 0:
            return

        sel_rows = self.__selected_rows
        cursor_row = table.cursor_row
        targets = sorted(sel_rows) if sel_rows else [cursor_row]
        try:
            for i in targets:
                func(self.__get_row_key(i))
        except docker.errors.APIError as e:
            self.context().notify(e.explanation or str(e), severity='error')
        finally:
            self.renew()
            self.__set_cursor_row(cursor_row)

    def action_refresh(self):
        self.renew()

    def action_sidebar(self):
        self.context().toggle_sidebar()

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

    def __update_footer(self, total):
        self.__total_label.update(f'Total: {total}')
        self.__update_selected_label()

    def __update_selected_label(self):
        self.__selected_label.update(f'Selected: {len(self.__selected_rows)}')

    def __toggle_row_sel(self, cursor_row=None, move_cursor=True):
        if cursor_row is None:
            cursor_row = self._table.cursor_row

        table = self._table
        rows = tuple(table.rows.items())
        row_key, row = rows[cursor_row]
        col_key, _ = next(iter(table.columns.items()))

        sel_rows = self.__selected_rows
        if cursor_row in sel_rows:
            sel_rows.remove(cursor_row)
            row.label = Text(f'{cursor_row + 1: <{self.__num_space_pad}}')
        else:
            sel_rows.add(cursor_row)
            row.label.style = Style(color='#FA8072')
            row.label.set_length(len(self.SELECTED_SYMBOL))
            row.label.append('[✓]')

        cell_val = table.get_cell(row_key, col_key)
        table.update_cell(row_key, col_key, cell_val, update_width=True)
        if move_cursor:
            table.action_cursor_down()

    def __selection_size(self):
        if self._table.row_count == 0:
            return 0
        return len(self.__selected_rows) or 1

    def __get_row_key(self, row_index):
        rows = tuple(self._table.rows.items())
        row_key, _ = rows[row_index]
        return row_key.value

    def __get_row_item(self, row_index):
        return self.get_item(self.__get_row_key(row_index))


class ImagesScreen(ResourceScreen):
    SCREEN_ID = 'images-screen'
    TITLE = 'Images'
    ITEM_NAME = 'image'
    COLUMNS = ('Short ID', 'Tags')

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

    def remove_item(self, key):
        self._cli.images.remove(key)

    def open_details(self, image):
        self.context().set_details_screen(image, 'Image details', 'set_images_screen')


class ContainersScreen(ResourceScreen):
    SCREEN_ID = 'containers-screen'
    TITLE = 'Containers'
    ITEM_NAME = 'container'
    COLUMNS = ('Short ID', 'Name', 'Image', 'Status')

    BINDINGS = ResourceScreen.BINDINGS + [
        Binding("u", "start", "Start"),
        Binding("x", "stop", "Stop"),
        Binding("t", "restart", "Restart"),
    ]

    def action_start(self):
        self.apply_to_selection(lambda key: self.get_item(key).start())

    def action_stop(self):
        self.apply_to_selection(lambda key: self.get_item(key).stop())

    def action_restart(self):
        self.apply_to_selection(lambda key: self.get_item(key).restart())

    def list_items(self):
        return self._cli.containers.list(all=True)

    def item_key(self, container):
        return container.id

    def item_row(self, container):
        # Like `docker ps`: the image name the container was created with.
        # (container.image would be an extra API call per row and fails if
        # the image has since been removed.)
        image_name = container.attrs.get('Config', {}).get('Image') or '<None>'
        return container.short_id, container.name, image_name, container.status

    def get_item(self, key):
        return self._cli.containers.get(key)

    def remove_item(self, key):
        self._cli.containers.get(key).remove()

    def open_details(self, container):
        self.context().set_details_screen(container, 'Container details', 'set_containers_screen')


class NetworksScreen(ResourceScreen):
    SCREEN_ID = 'networks-screen'
    TITLE = 'Networks'
    ITEM_NAME = 'network'
    COLUMNS = ('Short ID', 'Name', 'Driver', 'Scope')

    def list_items(self):
        return self._cli.networks.list()

    def item_key(self, network):
        return network.id

    def item_row(self, network):
        attrs = network.attrs
        return network.short_id, network.name, attrs.get('Driver', ''), attrs.get('Scope', '')

    def get_item(self, key):
        return self._cli.networks.get(key)

    def remove_item(self, key):
        self._cli.networks.get(key).remove()

    def open_details(self, network):
        self.context().set_details_screen(network, 'Network details', 'set_networks_screen')


class VolumesScreen(ResourceScreen):
    SCREEN_ID = 'volumes-screen'
    TITLE = 'Volumes'
    ITEM_NAME = 'volume'
    COLUMNS = ('Name', 'Driver', 'Mountpoint')

    def list_items(self):
        return self._cli.volumes.list()

    def item_key(self, volume):
        return volume.name

    def item_row(self, volume):
        attrs = volume.attrs
        return volume.name, attrs.get('Driver', ''), attrs.get('Mountpoint', '')

    def get_item(self, key):
        return self._cli.volumes.get(key)

    def remove_item(self, key):
        self._cli.volumes.get(key).remove()

    def open_details(self, volume):
        self.context().set_details_screen(volume, 'Volume details', 'set_volumes_screen')


class DetailsScreen(Screen, ScreenStateBase):
    BINDINGS = [
        Binding("escape", "exit", "Go back"),
        Binding("s", "sidebar", "Sidebar"),
    ]

    def __init__(self, ctx, item, title, back):
        Screen.__init__(self, id='details-screen')
        ScreenStateBase.__init__(self, ctx)
        self.__item = item
        self.__title = title
        self.__back = back

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
                if context.is_sidebar_visible():
                    context.hide_sidebar()
                else:
                    getattr(context, self.__back)()


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
