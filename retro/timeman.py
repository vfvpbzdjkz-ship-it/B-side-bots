"""Time management: the :class:`TimeLimits` container and the search budget.

The UCI driver fills a :class:`TimeLimits` from the ``go`` command and hands it to
the harness.  The harness turns the limits into a wall-clock *deadline* that
engines can poll cooperatively (``limits.time_up()``) so they bail out of search
before they flag.  The harness also enforces a hard thread deadline as a backstop.

All public times here are in **seconds** (UCI sends milliseconds; the driver
converts on the way in).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

# Tuning constants for the "no movetime given" case.
DEFAULT_BUDGET = 1.0      # seconds, when we know nothing about the clock
MIN_BUDGET = 0.02         # never think for less than this
MAX_BUDGET = 8.0          # never burn more than this on one move
SAFETY_MARGIN = 0.05      # shave this off movetime so we answer before the flag


@dataclass
class TimeLimits:
    """Everything the engine is told about how long it may think.

    Times are in seconds.  ``deadline`` is a ``time.monotonic`` timestamp set by
    :meth:`start`; engines should poll :meth:`time_up` inside their search loops.
    """

    movetime: Optional[float] = None
    wtime: Optional[float] = None
    btime: Optional[float] = None
    winc: float = 0.0
    binc: float = 0.0
    depth: Optional[int] = None
    deadline: Optional[float] = None

    def budget(self, white_to_move: bool) -> float:
        """Return how many seconds we are allowed to spend on this move."""
        if self.movetime is not None:
            return max(MIN_BUDGET, self.movetime - SAFETY_MARGIN)

        remaining = self.wtime if white_to_move else self.btime
        inc = self.winc if white_to_move else self.binc
        if remaining is None:
            # No clock info at all (e.g. plain ``go`` or ``go depth N``).
            return DEFAULT_BUDGET

        # Classic "spend a thirtieth of the clock plus most of the increment".
        spend = remaining / 30.0 + 0.7 * inc
        # Never gamble more than ~80% of what is left on a single move.
        ceiling = min(MAX_BUDGET, max(MIN_BUDGET, remaining * 0.8))
        return _clamp(spend, MIN_BUDGET, ceiling)

    def start(self, white_to_move: bool) -> float:
        """Arm the cooperative deadline and return the chosen budget (seconds)."""
        b = self.budget(white_to_move)
        self.deadline = time.monotonic() + b
        return b

    def time_up(self) -> bool:
        """True once the cooperative deadline has passed."""
        return self.deadline is not None and time.monotonic() >= self.deadline

    def remaining(self) -> float:
        """Seconds left before the deadline (``inf`` if no deadline armed)."""
        if self.deadline is None:
            return float("inf")
        return self.deadline - time.monotonic()


def _clamp(value: float, low: float, high: float) -> float:
    if high < low:
        high = low
    return max(low, min(high, value))
