from rich.panel import Panel
import rich.spinner
import asyncio
import time
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Markdown, Static


def text_streamer(delay: float = 0.05):
    text = """
# Clausit inpubesque igitur nemorosis

## Quodque conceptus vultum conticuit

Lorem markdownum Venerem totis vox: metuenda novata. Una utrimque tamen et Styga
restabat septem calescit. Cum sinus eheu satiaque undis est vocant saxoque
cinximus? Cum sinus novi honorat, statuunt, quadripedes vetus Aeneia Almo rupta
dat adsiduae et cornua, ego retexi. Imagine corpus.

- Letalem quaesitae
- Nervo satum undis mergor venite naiadum
- Haud nec

Caelum et quicquam pectus est cineres quondam. Danais nullique divinae et terrae
manus clamor, nubila magnanimus cessit torum modo lumina `resolutionProm`
sepulta. Corpora miserabile suis tamen, validis Pico pede oculosque spoliata
senserat, et regione paelex vix recingitur mearum. Ignorans arvum, latuit
eludere. Urbem sive, **sex sonat**, negata ne gente ferret fidequemunera
`bitmap_atm` odoribus.

Hoc nulla: haec gerebam iuvenis tecum haemonii semina; robore e! Fatis non
toroque amicas spectant Siqua carceris. Qua verba Gratia dixit, suos luce oro
[sum coniunctior viso](#quodque-conceptus-vultum-conticuit) certumque Alpes, et
nondum novo. In ab mota hanc vera sum, adspergine iam spectas.

## Nullaque augentur omnia

Manum laeva suspiria enim requies circumtulit fumis, iterabat vestrumque erit.
Ministri flumina albis! Nisi cedere suum umidus distent sanctaque astris, posse
acuti traxit erat harena. Habuit adeo Procne iam Troia tellus dixerat trita
facinus talisque qui.

> Dixi indignis est *ense est* neque quo mollibus volucrum; manu? Carinae cum
> petit si patres torvos quique ab norant signa. Rore lux orbes sed Hectora
> stagnata, iuventae hae tempora; dare funera donec obstipuit?

Loqui arreptum Achille Ilion. Consorte tenebat, dare prece paelice? Cum misere
patriae, fortius antra `systray_wins` lingua prima, conamine illo huic. Et
inculpata inquit quae sua iamque culmen Cydoneasque regno et, suum exempla adde
rerum."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(delay)


class SpinnerWidget(Static):
    def __init__(self, text: str = "Running..."):
        self._spinner = rich.spinner.Spinner("dots", text=text)
        panel = Panel(
            self._spinner,
            title="tool",
            border_style="#f9e2af",
        )
        super().__init__(panel)

    def on_mount(self) -> None:
        self.set_interval(1 / 10, self.refresh)


class RowbotTuiApp(App):
    """Textual TUI app for Rowbot chat frontend."""

    TITLE = "Rowbot"
    SUB_TITLE = "chat with Excel with ease"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
    ]

    CSS = """
    #input-box {
        dock: bottom;
        height: auto;
        width: 100%;
        margin: 0 0 2 0;
        align-horizontal: center;
    }

    #message_input {
        width: 80%;
    }

    #send_button {
        width: 20%;
        color: #11111b;
        background: #fab387;
        border: blank;
    }

    .message-row {
        width: 100%;
        height: auto;
    }

    .message-row.user {
        align-horizontal: right;
    }

    .message-row.ai {
        align-horizontal: left;
    }

    .bubble {
        width: auto;
        max-width: 75%;
        height: auto;
        margin: 1 0;
        padding: 1 3;
    }

    .bubble.user {
        border: round #cba6f7;
        color: #cba6f7;
    }

    .bubble.ai {
        color: #94e2d5;
    }

    .bubble MarkdownBlock {
        width: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(id="conversation")
        with Horizontal(id="input-box"):
            yield Input(placeholder="Enter your message...", id="message_input")
            yield Button(label="Send", variant="success", id="send_button")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send_button":
            await self.process_conversation()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "message_input":
            await self.process_conversation()

    async def process_conversation(self) -> None:
        message_input = self.query_one("#message_input", Input)
        text = message_input.value.strip()
        if not text:
            return

        message_input.value = ""

        conversation = self.query_one("#conversation", VerticalScroll)
        await conversation.mount(
            Horizontal(
                Markdown(text, classes="bubble user"),
                classes="message-row user",
            )
        )
        ai_message = Markdown("", classes="bubble ai")
        await conversation.mount(Horizontal(ai_message, classes="message-row ai"))
        conversation.anchor()

        stream = Markdown.get_stream(ai_message)
        try:
            for chunk in text_streamer(delay=0.02):
                await stream.write(chunk)
        finally:
            await stream.stop()

        tool_widget = SpinnerWidget("get_excel(name='abc.xlsx')")
        await conversation.mount(tool_widget)
        conversation.scroll_end()
        await asyncio.sleep(6)
        await tool_widget.remove()
        await conversation.mount(
            Static(
                Panel(
                    "[italic]get_excel[/italic] -> jksadsfljadfl...",
                    title="tool",
                    border_style="#f9e2af",
                )
            )
        )
        conversation.anchor()


def run_tui_app() -> None:
    """Run the Rowbot TUI app."""
    RowbotTuiApp().run()


if __name__ == "__main__":
    run_tui_app()
