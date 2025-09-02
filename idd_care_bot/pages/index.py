import reflex as rx
import httpx
from reflex.event import EventCallback

from idd_care_bot.components.sidebar import sidebar


def sidebar_action(text: str, icon: str, action: EventCallback) -> rx.Component:
    return rx.button(
        rx.hstack(
            rx.icon(icon),
            rx.text(text, size="4"),
            width="100%",
            align="center",
            style={
                "_hover": {
                    "bg": rx.color("accent", 4),
                    "color": rx.color("accent", 11),
                },
                "border-radius": "0.5em",
            },
        ),
        variant="soft",
        size="4",
        width="100%",
        on_click=action,
    )


class Message(rx.Base):
    role: str  # "user" or "assistant"
    content: str

    def __repr__(self) -> str:
        return f"{self.role=},{self.content=}"


class ChatState(rx.State):
    name: str = rx.LocalStorage(name="idd-care-bot-user.name")
    email: str = rx.LocalStorage(name="idd-care-bot-user.email")

    messages: list[Message] = []
    user_input: str = ""
    loading: bool = False

    @rx.event
    def on_mount(self):
        print("on mount")
        if not self.name or not self.email:
            rx.redirect("/")

    @rx.event
    def new_chat(self):
        """Start a new chat conversation"""
        self.messages = []
        self.user_input = ""
        self.loading = False

    @rx.event
    def download_chat(self):
        """Handle form submission"""
        if len(self.messages) == 0:
            return
        content = "\n".join([f"{msg}" for msg in self.messages])
        return rx.download(data=content, filename=f"{self.name} ({self.email}).chat")

    @rx.event
    async def send_message(self):
        if not self.user_input.strip() or self.loading:
            return

        # Add user message
        self.messages.append(Message(role="user", content=self.user_input))
        query = self.user_input
        self.user_input = ""
        self.loading = True
        self.messages.append(Message(role="assistant", content="• • •"))
        yield

        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "http://0.0.0.0:8000/chat",  # FastAPI backend
                    json={"query": query},
                    timeout=30,
                )
                r.raise_for_status()
                data = r.json()

            # Assistant response
            self.messages.pop()
            self.messages.append(
                Message(role="assistant", content=data.get("answer", ""))
            )

        except Exception as e:
            self.messages.append(Message(role="assistant", content=f"⚠️ Error: {e}"))
        finally:
            self.loading = False


def message_bubble(msg: Message) -> rx.Component:
    is_user = msg.role == "user"

    box = rx.box(
        rx.markdown(
            msg.content,
            size="1",
            color=rx.cond(is_user, "white", "black"),
            white_space="pre-wrap",
        ),
        background_color=rx.cond(is_user, "var(--blue-9)", "var(--gray-3)"),
        padding="0px 10px",
        border_radius="10px",
        min_width="10%",
        max_width="75%",
        margin="10px 0px",
    )

    return rx.cond(
        is_user,
        rx.hstack(
            rx.spacer(),
            box,
        ),
        rx.hstack(
            box,
            rx.spacer(),
        ),
    )


@rx.page(route="/chat")  # type: ignore
def chat_page() -> rx.Component:
    return rx.hstack(
        sidebar(
            actions=[
                sidebar_action(
                    "New Chat",
                    "bot-message-square",
                    ChatState.new_chat,  # type: ignore
                ),
            ],
            post_actions=[
                sidebar_action(
                    "Download Chat",
                    "download",
                    ChatState.download_chat,  # type: ignore
                )
            ],
            user_name=ChatState.name,
            user_email=ChatState.email,
        ),
        rx.center(
            rx.vstack(
                # Chat messages
                rx.box(
                    rx.foreach(ChatState.messages, message_bubble),
                    overflow_y="auto",
                    height="70vh",
                    width="100%",
                    background_color="white",
                    border="1px solid #e2e8f0",
                    border_radius="10px",
                    padding="16px",
                ),
                # Input box
                rx.form.root(
                    rx.hstack(
                        rx.input(
                            value=ChatState.user_input,
                            placeholder="Type your message...",
                            on_change=ChatState.set_user_input,
                            width="100%",
                            height="50px",
                            padding="12px",
                            border_radius="10px",
                            border="1px solid #cbd5e0",
                        ),
                        rx.button(
                            rx.cond(ChatState.loading, rx.spinner(), rx.icon("send")),
                            on_click=ChatState.send_message,
                            is_disabled=ChatState.loading,
                            color_scheme="blue",
                            padding_x="20px",
                            padding_y="12px",
                            height="50px",
                            border_radius="10px",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    on_submit=ChatState.send_message,
                ),
                spacing="4",
                width="100%",
                max_width="800px",
            ),
            padding="20px",
            background_color="var(--gray-1)",
            min_height="100vh",
            width="100%",
        ),
        width="100%",
    )
