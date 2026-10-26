"""Declarative base shared by every module's persistence layer."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
