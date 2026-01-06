from textual import on, work
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Label, Static

ERROR_TEXT = """
An error has occurred. To continue:

Press Enter to return to Windows, or

Press CTRL+ALT+DEL to restart your computer. If you do this,
you will lose any unsaved information in all open applications.

Error: 0E : 016F : BFF9B3D4
"""


class BSOD(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Pop screen")]

    def compose(self) -> ComposeResult:
        yield Static(" Windows ", id="title")
        yield Static(ERROR_TEXT)
        yield Static("Press any key to continue [blink]_[/]", id="any-key")


class QuestionScreen(Screen[bool]):
    """Screen with a parameter."""

    def __init__(self, question: str) -> None:
        self.question = question
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(self.question)
        yield Button("Yes", id="yes", variant="success")
        yield Button("No", id="no")

    @on(Button.Pressed, "#yes")
    def handle_yes(self) -> None:
        self.dismiss(True)  

    @on(Button.Pressed, "#no")
    def handle_no(self) -> None:
        self.dismiss(False)  


class QuestionsApp(App):
    """Demonstrates wait_for_dismiss"""

    CSS_PATH = "questions01.tcss"

    @work  
    async def on_mount(self) -> None:
        self.push_screen(BSOD())

        # if await self.push_screen_wait(  
        #     QuestionScreen("Do you like Textual?"),
        # ):
        #     # self.notify("Good answer!")
        #     self.switch_screen(BSOD())
        # else:
        #     self.notify(":-(", severity="error")


if __name__ == "__main__":
    app = QuestionsApp()
    app.run()