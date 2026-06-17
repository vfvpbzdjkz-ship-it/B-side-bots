"""Safety wrapper + budgeting — the single most important file for stability.

``safe_choose`` guarantees three things no matter how badly an engine misbehaves:

* it always returns a **legal** move (or ``None`` only when the game is already
  over and there are no legal moves),
* it never lets the engine run past its time budget (a worker thread with a hard
  deadline, on top of the cooperative ``limits.time_up()`` checks engines make),
* it never crashes the process — any exception falls back to a random legal move.
"""

from __future__ import annotations

import logging
import random
import threading
from typing import Optional

import chess

from .timeman import TimeLimits

log = logging.getLogger("retro.harness")

# A little grace on top of the cooperative budget before we pull the plug on the
# worker thread.  Cooperative checks should stop the engine first; this is the
# backstop for an engine that blows past a single un-checked node.
HARD_DEADLINE_GRACE = 0.20


def safe_choose(engine, board: chess.Board, limits: TimeLimits) -> Optional[chess.Move]:
    """Return a guaranteed-legal move for ``board``, or ``None`` if game over."""
    legal = list(board.legal_moves)
    if not legal:
        return None  # game already over; the driver decides what to print

    fallback = random.choice(legal)  # guaranteed-legal escape hatch
    try:
        move = run_with_deadline(engine.choose_move, board, limits)
        if move is not None and move in legal:
            return move
        if move is not None:
            log.warning("engine returned illegal move %s; using fallback", move)
    except Exception:  # noqa: BLE001 - we must never crash on Lichess
        log_exception()
    return fallback  # never crash, never return illegal/none


def run_with_deadline(choose_move, board: chess.Board, limits: TimeLimits):
    """Run ``choose_move`` on a copy of the board with a hard wall-clock deadline.

    The engine searches a *copy*, so a timed-out worker can never corrupt the
    board the driver is tracking.  ``limits`` is shared, so the worker sees the
    same cooperative deadline and should return its best-so-far on its own.
    """
    budget = limits.start(board.turn == chess.WHITE)
    # Copy *with* the move stack so strategies that react to the opponent's last
    # move (e.g. MIRROR) can read board.peek(); a timed-out worker still only ever
    # mutates this copy, never the board the driver is tracking.
    work_board = board.copy(stack=True)

    result: dict = {}

    def worker() -> None:
        try:
            result["move"] = choose_move(work_board, limits)
        except Exception as exc:  # noqa: BLE001 - reported back to caller
            result["exc"] = exc

    thread = threading.Thread(target=worker, name="retro-search", daemon=True)
    thread.start()
    thread.join(budget + HARD_DEADLINE_GRACE)

    if thread.is_alive():
        # Worker ignored the cooperative deadline; abandon it (daemon, will die
        # with the process) and let the caller fall back to a legal move.
        log.warning("search exceeded hard deadline; abandoning worker")
        raise TimeoutError("search exceeded hard deadline")

    if "exc" in result:
        raise result["exc"]
    return result.get("move")


def log_exception() -> None:
    """Log the current exception without ever propagating it."""
    log.exception("engine raised; falling back to a random legal move")
