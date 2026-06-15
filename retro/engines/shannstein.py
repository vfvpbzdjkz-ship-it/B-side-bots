"""SHANNSTEIN — Shannon Type-B (1950) + Bernstein (1957) fusion.

Selective forward pruning: at every node, score the legal moves with a cheap
``plausibility`` heuristic and recurse only on the top-K (Bernstein used ~7).
The tree stays narrow, so it can be searched deeper.  It authentically prunes
away the real best move when the cheap heuristic does not flag it.

The ``keep all when fewer than K`` fallback is mandatory: it guarantees the
engine always has a move to play in a near-forced position.
"""

from __future__ import annotations

from typing import List

import chess

from ..common.evalutil import MATE, eval_stm
from ..common.moveutil import pick_best, plausibility
from ..timeman import TimeLimits

K = 7            # Bernstein's "plausible move" budget per node
MAX_DEPTH = 4    # fixed nominal depth; iterative deepening respects the clock


class Shannstein:
    name = "SHANNSTEIN"
    author = "B-Side Engines"

    def new_game(self) -> None:
        pass

    def choose_move(self, board: chess.Board, limits: TimeLimits) -> chess.Move:
        limit_depth = limits.depth or MAX_DEPTH
        root_moves = self._plausible_moves(board)
        best_move = root_moves[0]
        for depth in range(1, limit_depth + 1):
            scored = self._root_search(board, root_moves, depth, limits)
            if scored is None:  # incomplete depth -> keep the previous best
                break
            best_move = pick_best(scored)
        return best_move

    def _root_search(self, board, root_moves, depth, limits):
        # Full window per root move so the scored list is exact for pick_best.
        scored = []
        for move in root_moves:
            board.push(move)
            val = -self._search(board, depth - 1, -MATE * 2, MATE * 2, limits)
            board.pop()
            if limits.time_up():
                return None
            scored.append((move, val))
        return scored

    def _search(self, board, depth, alpha, beta, limits) -> float:
        if board.is_checkmate():
            return -MATE
        if board.is_game_over():
            return 0.0
        if depth <= 0 or limits.time_up():
            return eval_stm(board)

        best = -MATE * 2
        for move in self._plausible_moves(board):
            board.push(move)
            val = -self._search(board, depth - 1, -beta, -alpha, limits)
            board.pop()
            if val > best:
                best = val
            if val > alpha:
                alpha = val
            if alpha >= beta:
                break
            if limits.time_up():
                break
        return best

    @staticmethod
    def _plausible_moves(board: chess.Board) -> List[chess.Move]:
        """Top-K moves by plausibility, or *all* of them when there are < K."""
        moves = list(board.legal_moves)
        moves.sort(key=lambda m: plausibility(board, m), reverse=True)
        # Mandatory fallback: never prune below the full move list when forced.
        return moves[:K] if len(moves) >= K else moves
