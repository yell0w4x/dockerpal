from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.widgets import DataTable, Footer, Header, Static, Label, Button, TextArea, ListView, ListItem
from textual.color import Color
from textual.theme import Theme
from textual import events
from textual.screen import Screen, ModalScreen
from textual._context import active_app
from textual.reactive import reactive
from textual.containers import Horizontal, VerticalGroup, Vertical, VerticalScroll, Container
from textual.binding import Binding
from textual import on, work
from python_event_bus import EventBus
from time import monotonic
from rich.text import Text
from rich.style import Style

import docker

from dockerpal.screens.fsm import ScreenFSM, SplashScreen


arctic_theme = Theme(
    name="arctic",
    primary="#88C0D0",
    secondary="#81A1C1",
    accent="#B48EAD",
    foreground="#D8DEE9",
    background="#2E3440",
    success="#A3BE8C",
    warning="#EBCB8B",
    error="#BF616A",
    surface="#3B4252",
    panel="#434C5E",
    dark=True,
    variables={
        "block-cursor-text-style": "none",
        "footer-key-foreground": "#88C0D0",
        "input-selection-background": "#81a1c1 35%",
    },
)


class DockerPalApp(App):
    CSS = """
    DataTable {
        # margin-bottom: 1;  /* Leave space for footer */
    }
    
    #table-footer {
        dock: bottom;
        height: 2;
        background: $panel;
        # border-top: solid $primary;
        # padding: 0 1;
        align: center middle;
    }

    #table-footer Label {
        margin-right: 2;
    }

    #sidebar {
        margin-top: 1;
        dock: left;
        width: 15;
        height: 100%;
        # color: #0f2b41;
        display: none;
        # background: dodgerblue;
    }

    #initializing-label,#not-implemented-label {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }    
    """

    def __init__(self):
        super().__init__()
        active_app.set(self)

        cli = docker.from_env()
        self.__fsm = ScreenFSM(cli)


    def on_key(self, event: events.Key):
        match event.key:
            case 'q':
                self.exit()

        self.__fsm.on_state_key(event)


    async def on_mount(self):
        self.title = 'DockerPal'
        self.register_theme(arctic_theme)
        self.theme = 'arctic'
        self.push_screen(SplashScreen())

        # loop = asyncio.get_running_loop()
        # images_list =  await loop.run_in_executor(None, lambda: self.__docker_cli.images.list())
        self.__fsm.set_images_screen()


    def action_toggle_dark(self):
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"    


def app():
    app = DockerPalApp()
    app.run()
