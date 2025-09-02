from typing import Callable

import reflex as rx

from .components.sidebar import sidebar


class TemplateState(rx.State):
    actions: list[rx.Component] = []
    post_actions: list[rx.Component] = []


def template(page: Callable[[], rx.Component]) -> rx.Component:
    return rx.hstack(
        sidebar(TemplateState.actions, TemplateState.post_actions),
        rx.container(page()),
        width="100%",
    )
