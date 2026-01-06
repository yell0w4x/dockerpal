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
        yield ListItem(Label('Volumens'), id='volumens-sidebar-item')


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
    def __init__(self, docker_cli):
        self.__state = None
        self.__docker_cli = docker_cli


    def set_images_screen(self, images_list=None):
        self.set_state(ImagesScreen(self, self.__docker_cli))


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


class ImagesScreen(Screen, ScreenStateBase):
    current_row = None
    SELECTED_SYMBOL = '[✓]'

    BINDINGS = [
        Binding("d,delete", "delete", "Delete"),
        Binding("r", "refresh", "Refresh"),
        Binding("space", "select_row", "Select row"),
        # Binding("enter", "image_details", "Details"),
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

    def __init__(self, ctx, docker_cli, images_list=None):
        Screen.__init__(self, id='images-screen')
        ScreenStateBase.__init__(self, ctx)
        self.__cli = docker_cli
        table = DataTable(id='images-table', cursor_type='row', zebra_stripes=False)
        table.add_column(label='Short ID')
        table.add_column('Tags')
        self.__double_press = dict()
        self.__table = table
        self.__num_space_pad = 0
        self.__selected_rows = set()
        self.__total_label = Label()
        self.__selected_label = Label()
        self.renew(images_list)


    def renew(self, images_list=None):
        def tag(image):
            return ', '.join(image.tags) if image.tags else '<None>'

        def short_id(image):
            return image.short_id.split(':')[1]

        def full_id(image):
            return image.id.split(':')[1]

        images = self.__cli.images.list() if images_list is None else images_list
        table = self.__table
        table.clear()
        pad = self.__num_space_pad = len(str(len(images))) + len(self.SELECTED_SYMBOL) + 2
        {table.add_row(short_id(image), tag(image), key=full_id(image), label=f'{i: <{pad}}'): image for i, image in enumerate(images, 1)}
        self.__update_footer()


    def compose(self):
        yield from compose_sidebar()
        yield Header(name='Images')
        yield self.__table
        # yield Horizontal(self.__total_label, self.__selected_label, id='table-footer')
        with Horizontal(id="table-footer"):
            yield self.__total_label
            yield self.__selected_label
        yield Footer()


    def on_state_enter(self, data=None):
        self.context().set_subtitle('Images')
        self.context().switch_screen(self)
        if ImagesScreen.current_row is not None:
            self.__set_cursor_row(ImagesScreen.current_row)


    def on_state_key(self, event: events.Key):
        table = self.__table
        context = self.context()
        match event.key:
            case 'escape' | 'q':
                context.exit()
            case 'enter':
                if context.is_sidebar_visible():
                     sidebar = context.app().get_child_by_id('sidebar')
                     match sidebar.highlighted_child.id:
                        case 'images-sidebar-item':
                            pass
                        case 'containers-sidebar-item':
                            context.notify('Not implemented yet.', severity='warning')
                        case 'networks-sidebar-item':
                            context.notify('Not implemented yet.', severity='warning')
                        case 'volumens-sidebar-item':
                            context.notify('Not implemented yet.', severity='warning')
                     
                else:
                    ImagesScreen.current_row = table.cursor_row
                    context.set_image_details_screen(self.__get_row_image(table.cursor_row))

    
    def action_select_all(self):
        table = self.__table
        sel_rows = self.__selected_rows
        sel_rows.clear()
        for i in range(len(table.rows)):
            self.__toggle_row_sel(i, move_cursor=False)
        self.__update_selected_label()


    def action_deselect_all(self):
        table = self.__table
        self.__selected_rows = {i for i in range(len(table.rows))}
        for i in range(len(table.rows)):
            self.__toggle_row_sel(i, move_cursor=False)
        self.__update_selected_label()


    def action_invert_selection(self):
        table = self.__table
        for i in range(len(table.rows)):
            self.__toggle_row_sel(i, move_cursor=False)
        self.__update_selected_label()


    def action_select_row(self):
        self.__toggle_row_sel()
        self.__update_selected_label()


    def action_down(self):
        self.__table.action_cursor_down()

   
    def action_up(self):
        self.__table.action_cursor_up()


    def action_page_down(self):
        self.__table.action_page_down()


    def action_page_up(self):
        self.__table.action_page_up()


    def action_go_up(self):
        table = self.__table
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
        self.__table.action_scroll_bottom()


    def action_delete(self):
        def remove_image(row_index):
            rows = tuple(table.rows.items())
            row_key, _ = rows[row_index]
            self.__cli.images.remove(row_key.value)

        table = self.__table
        sel_rows = self.__selected_rows
        cursor_row = table.cursor_row
        try:
            if not sel_rows:
                remove_image(cursor_row)
            else:
                for i in sel_rows:
                    remove_image(i)
                sel_rows.clear()
        except docker.errors.APIError as e:
            self.context().notify(e.explanation, severity='error')
        else:
            self.renew()
            self.__set_cursor_row(cursor_row)
            self.__update_selected_label()


    def action_refresh(self):
        self.renew()


    def action_sidebar(self):
        self.context().toggle_sidebar()


    def on_mount(self):
        self.get_child_by_id('images-table').focus()


    def __set_cursor_row(self, row_index):
        table = self.__table
        if table.row_count > row_index:
            table.move_cursor(row=row_index)
        elif table.row_count > 0:
            table.move_cursor(row=table.row_count - 1)

    
    def __update_footer(self):
        self.__total_label.update(f'Total: {len(self.__cli.images.list())}')
        self.__selected_label.update(f'Selected: {len(self.__selected_rows)}')


    def __update_selected_label(self):
        self.__selected_label.update(f'Selected: {len(self.__selected_rows)}')


    def __toggle_row_sel(self, cursor_row=None, move_cursor=True):
        if cursor_row is None:
            cursor_row = self.__table.cursor_row

        table = self.__table
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

    
    def __get_row_image(self, row_index):
        rows = tuple(self.__table.rows.items())
        row_key, _ = rows[row_index]
        return self.__cli.images.get(row_key.value)


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
                sidebar = context.app().get_child_by_id('sidebar')
                match sidebar.highlighted_child.id:
                    case 'images-sidebar-item':
                        pass
                    case 'containers-sidebar-item':
                        context.notify('Not implemented yet.', severity='warning')
                    case 'networks-sidebar-item':
                        context.notify('Not implemented yet.', severity='warning')
                    case 'volumens-sidebar-item':
                        context.notify('Not implemented yet.', severity='warning')
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
