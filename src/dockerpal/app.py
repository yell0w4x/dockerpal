from textual.app import App
from textual.theme import Theme
from textual import events
from textual._context import active_app

import docker

from dockerpal.fsm import ScreenFSM, SplashScreen, ErrorScreen


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

    #initializing-label,#not-implemented-label,#error-label {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }    
    """

    def __init__(self):
        super().__init__()
        self.__fsm = None
        active_app.set(self)


    def on_key(self, event: events.Key):
        match event.key:
            case 'q':
                self.exit()

        if self.__fsm is None:
            return

        self.__fsm.on_state_key(event)


    async def on_mount(self):
        self.title = 'DockerPal'
        self.register_theme(arctic_theme)
        self.theme = 'arctic'

        try:
            cli = docker.from_env()
        except Exception as e:
            self.push_screen(ErrorScreen(f"Error connecting to Docker: {e}"))
            return
        else:
            self.__fsm = ScreenFSM(cli)

        self.push_screen(SplashScreen())
        self.__fsm.set_images_screen()


    def action_toggle_dark(self):
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"    


def app():
    app = DockerPalApp()
    app.run()
