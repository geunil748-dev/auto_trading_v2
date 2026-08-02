"""Persistable P4B.2A positive-close labels."""

from enum import StrEnum


class PositiveForwardCloseLabel(StrEnum):
    POSITIVE = "POSITIVE"
    NOT_POSITIVE = "NOT_POSITIVE"
