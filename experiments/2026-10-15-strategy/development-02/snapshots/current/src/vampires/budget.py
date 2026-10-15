"""Cooperative monotonic deadlines shared by generation, simulation, and search."""

from dataclasses import dataclass
from time import monotonic


class SearchTimeout(Exception):
    """Stop unfinished work without replacing the last completed decision."""


@dataclass(frozen=True)
class Deadline:
    expires_at: float
    clock: object = monotonic

    def check(self):
        if self.clock() >= self.expires_at:
            raise SearchTimeout


def checkpoint(check):
    if check is not None:
        check()
