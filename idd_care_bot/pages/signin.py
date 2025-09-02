import re

import reflex as rx

from ..models import User


class SigninState(rx.State):
    name: str = rx.LocalStorage(name="idd-care-bot-user.name")
    email: str = rx.LocalStorage(name="idd-care-bot-user.email")

    message: str = ""

    @rx.event
    def handle_submit(self, _: dict):
        """Handle form submission with validation."""
        # Basic validation
        if not self.name:
            self.message = "❌ Full name is required"
            return

        if not self.email or not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            self.message = "❌ Enter a valid email address"
            return

        try:
            with rx.session() as session:
                session.add(
                    User(
                        name=self.name,
                        email=self.email,
                    )
                )
                session.commit()

                return rx.redirect("/chat")
        except Exception as e:
            print(f"{e=}")


@rx.page(route="/")
def signin_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.form.root(
                rx.vstack(
                    # Logo + Title
                    rx.flex(
                        rx.image(
                            src="/logo.png",
                            width="2.5em",
                            height="auto",
                            border_radius="25%",
                        ),
                        rx.heading(
                            "Create an account",
                            size="6",
                            as_="h2",
                            text_align="left",
                            width="100%",
                        ),
                        direction="column",
                        justify="start",
                        spacing="4",
                        width="100%",
                    ),
                    # Full Name
                    rx.vstack(
                        rx.text("Full Name", size="3", weight="medium", width="100%"),
                        rx.input(
                            rx.input.slot(rx.icon("user")),
                            placeholder="Enter your full name",
                            name="name",  # 👈 important for form_data
                            size="3",
                            width="100%",
                            on_change=SigninState.set_name,  # type: ignore
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    # Email
                    rx.vstack(
                        rx.text(
                            "Email address", size="3", weight="medium", width="100%"
                        ),
                        rx.input(
                            rx.input.slot(rx.icon("mail")),
                            placeholder="name@gmail.com",
                            type="email",
                            name="email",  # 👈 important
                            size="3",
                            width="100%",
                            on_change=SigninState.set_email,  # type: ignore
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    # Submit button
                    rx.button(
                        "Register and Sign in",
                        size="3",
                        width="100%",
                        type="submit",
                    ),
                    # Validation message
                    rx.text(SigninState.message, color="red", size="3"),
                    spacing="6",
                    width="100%",
                ),
                on_submit=SigninState.handle_submit,  # type: ignore
            ),
            size="4",
            max_width="28em",
            width="100%",
        ),
        height="100vh",
    )
