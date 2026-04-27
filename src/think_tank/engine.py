"""Engine-facing functions for Think Tank.

The engine returns data and leaves display, prompting, and process concerns to adapters.
"""

from __future__ import annotations

from typing import TypedDict


class EngineStatus(TypedDict):
    product: str
    ready: bool


def get_engine_status() -> EngineStatus:
    """Return a minimal structured status for the bootstrap skeleton."""

    return {
        "product": "Think Tank",
        "ready": True,
    }

