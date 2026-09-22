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


def compose_sidebar():
    with ListView(id='sidebar'):
        yield ListItem(Label('Images'), id='images-sidebar-item')
        yield ListItem(Label('Containers'), id='containers-sidebar-item')
        yield ListItem(Label('Networks'), id='networks-sidebar-item')
        yield ListItem(Label('Volumes'), id='volumes-sidebar-item')


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

    def render(self):
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
        getattr(self, self.SIDEBAR_ITEMS[item.id])()


    def set_image_details_screen(self, image):
        self.set_state(ImageDetailsScreen(self, image))


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


    def send_event(self, event):
        self.__event_bus.publish(event)

    
    def set_subtitle(self, subtitle):
        self.__app().sub_title = subtitle


    def switch_screen(self, screen):
        self.__app().switch_screen(screen)
    

    def notify(self, message, severity='information'):
        self.__app().notify(message, severity=severity)


    def toggle_sidebar(self):
        app = self.__app()
        sidebar = app.get_child_by_id('sidebar')
        if sidebar.styles.display == 'none':
            sidebar.styles.display = 'block'
            if sidebar.can_focus:
                sidebar.focus()
        else:
            sidebar.styles.display = 'none'

        return sidebar.styles.display == 'block'


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
        yield from compose_sidebar()
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
            case 'escape' | 'q':
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
        self.apply_to_selection(self.remove_item)

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

    def __get_row_key(self, row_index):
        rows = tuple(self._table.rows.items())
        row_key, _ = rows[row_index]
        return row_key.value

    def __get_row_item(self, row_index):
        return self.get_item(self.__get_row_key(row_index))


class ImagesScreen(ResourceScreen):
    SCREEN_ID = 'images-screen'
    TITLE = 'Images'
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
        self.context().set_image_details_screen(image)


class ContainersScreen(ResourceScreen):
    SCREEN_ID = 'containers-screen'
    TITLE = 'Containers'
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
        image = container.image
        image_name = image.tags[0] if image is not None and image.tags else (
            image.short_id.split(':')[-1] if image is not None else '<None>')
        return container.short_id, container.name, image_name, container.status

    def get_item(self, key):
        return self._cli.containers.get(key)

    def remove_item(self, key):
        self._cli.containers.get(key).remove()

    def open_details(self, container):
        self.context().notify('Not implemented yet.', severity='warning')


class NetworksScreen(ResourceScreen):
    SCREEN_ID = 'networks-screen'
    TITLE = 'Networks'
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
        self.context().notify('Not implemented yet.', severity='warning')


class VolumesScreen(ResourceScreen):
    SCREEN_ID = 'volumes-screen'
    TITLE = 'Volumes'
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
        self.context().notify('Not implemented yet.', severity='warning')


class ImageDetailsScreen(Screen, ScreenStateBase):
    BINDINGS = [
        Binding("escape", "exit", "Go back"),
    ]

    def __init__(self, ctx, image):
        Screen.__init__(self, id='image-details-screen')
        ScreenStateBase.__init__(self, ctx)
        self.__image = image


    def on_mount(self):
        self.get_child_by_id('image-details').focus()


    def on_state_enter(self, data=None):
        if data is not None:
            self.__image = data

        self.context().set_subtitle('Image details')
        self.context().switch_screen(self)


    def compose(self):
        try:        
            yield from compose_sidebar()
            yield Header()
            yield Footer()
            details = json.dumps(self.__image.attrs, indent=4)
            yield TextArea(details, read_only=True, language='json', id='image-details')
        except json.JSONDecodeError as e:
            yield TextArea(f'Unable to parse image details: {e}', read_only=True, language='html', id='image-details')
            self.context().notify(f'Unable to parse image details: {e}', severity='error')
        except Exception as e:
            yield TextArea(f'Unable to parse image details: {e}', read_only=True, language='html', id='image-details')
            self.context().notify(str(e), severity='error')


    def on_state_key(self, event: events.Key):
        context = self.context()
        match event.key:
            case 'enter':
                if context.is_sidebar_visible():
                    context.activate_sidebar_item()
            case 'escape':
                context.set_images_screen()
            case 's':
                context.toggle_sidebar()


class SplashScreen(Screen):
    def compose(self):
        yield Grid(Label("Initializing...", id='initializing-label'), id="splash-screen")


class NotImplementedScreen(Screen):
    def compose(self):
        yield Grid(Label("Not Implemented", id='not-implemented-label'), id="not-implemented-screen")


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


class QuitScreen(ModalScreen):
    """Screen with a dialog to quit."""

    def compose(self):
        yield Grid(
            Label("Are you sure you want to quit?", id="question"),
            Button("Quit", variant="error", id="quit"),
            Button("Cancel", variant="primary", id="cancel"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.app.exit()
        else:
            self.app.pop_screen()
