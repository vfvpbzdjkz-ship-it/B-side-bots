"""KNEEJERK — 1-ply tapered-eval proof of concept.

Pure positional "intuition", zero lookahead: try every legal move, statically
score the resulting position with the tapered PST eval, and play the best.  The
PeSTO tables do all the work — shockingly coherent development, then it hangs a
piece to any two-move tactic.
"""

from __future__ import annotations

import chess

from ..common.evalutil import eval_stm
from ..common.moveutil import pick_best
from ..timeman import TimeLimits


class KneeJerk:
    name = "KNEEJERK"
    author = "B-Side Engines"

    def new_game(self) -> None:
        pass

    def choose_move(self, board: chess.Board, limits: TimeLimits) -> chess.Move:
        scored = []
        for move in board.legal_moves:
            board.push(move)
            # eval_stm after the push is from the opponent's view; negate to get
            # the score from our point of view.
            scored.append((move, -eval_stm(board)))
            board.pop()
        return pick_best(scored)  # max with random tiebreak
