from typing import Optional
import reflex as rx
import sqlmodel


class User(rx.Model, table=True):
    name: str
    email: str
    chats: Optional["Chat"] = sqlmodel.Relationship(back_populates="user")


class Chat(rx.Model, table=True):
    user_id: int = sqlmodel.Field(foreign_key="user.id")
    user: Optional[User] = sqlmodel.Relationship(back_populates="chats")

    messages: Optional["Message"] = sqlmodel.Relationship(back_populates="chat")


class Message(rx.Model, table=True):
    role: str
    text: str
    chat_id: int = sqlmodel.Field(foreign_key="chat.id")
    chat: Optional[Chat] = sqlmodel.Relationship(back_populates="messages")
