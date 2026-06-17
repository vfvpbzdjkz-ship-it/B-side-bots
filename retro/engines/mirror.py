"""MIRROR — the parrot.

Plays the vertically-mirrored copy of the opponent's previous move (White's
``e2e4`` becomes Black's ``e7e5``), which keeps a symmetrical game symmetrical for
as long as it can.  The moment the mirror image is illegal — or there is no move to
mirror yet — it shrugs and hands the decision to a *random* one of the other
engines.  Designed to play **Black** (mirroring whoever just moved).
"""

from __future__ import annotations

import random

import chess

from ..timeman import TimeLimits


class Mirror:
    name = "MIRROR"
    author = "B-Side Engines"

    def new_game(self) -> None:
        pass

    def choose_move(self, board: chess.Board, limits: TimeLimits) -> chess.Move:
        mirrored = self._mirror_move(board)
        if mirrored is not None:
            return mirrored
        return self._random_engine_move(board, limits)

    @staticmethod
    def _mirror_move(board: chess.Board):
        """The vertical mirror of the opponent's last move, if it is legal here."""
        if not board.move_stack:
            return None  # nothing to mirror (we are on move, opponent hasn't played)
        last = board.peek()
        candidate = chess.Move(
            chess.square_mirror(last.from_square),
            chess.square_mirror(last.to_square),
            promotion=last.promotion,
        )
        return candidate if candidate in board.legal_moves else None

    @staticmethod
    def _random_engine_move(board: chess.Board, limits: TimeLimits) -> chess.Move:
        """Mirroring failed — delegate to a random sibling engine."""
        from . import ENGINES  # local import avoids a registry import cycle

        names = [name for name in ENGINES if name != "mirror"]
        engine = ENGINES[random.choice(names)]()
        return engine.choose_move(board, limits)
