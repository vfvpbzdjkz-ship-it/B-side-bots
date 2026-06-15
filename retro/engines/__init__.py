"""Engine registry: ``ENGINE=<name>`` selects which strategy the driver loads."""

from __future__ import annotations

from typing import Dict, Type

from .beeline import Beeline
from .copybook import Copybook
from .kneejerk import KneeJerk
from .shannstein import Shannstein
from .turampion import Turampion

# name -> class.  Keys are lower-case; the UCI driver lower-cases the env var.
ENGINES: Dict[str, Type] = {
    "turampion": Turampion,
    "shannstein": Shannstein,
    "copybook": Copybook,
    "kneejerk": KneeJerk,
    "beeline": Beeline,
}

DEFAULT_ENGINE = "kneejerk"


def get_engine(name: str):
    """Instantiate an engine by (case-insensitive) name."""
    key = (name or DEFAULT_ENGINE).strip().lower()
    if key not in ENGINES:
        raise KeyError(
            f"unknown engine {name!r}; choose one of {', '.join(sorted(ENGINES))}"
        )
    return ENGINES[key]()


def engine_names():
    return sorted(ENGINES)
