"""BEELINE — king-tropism gimmick with a motor.

Evaluation = material + tapered PST + a *tropism* term that rewards every piece
for being near the enemy king, plus bonuses for attackers in the king's ring and
for giving check.  A shallow 2-3 ply alpha-beta keeps it from simply donating the
pieces it throws forward.  Material is weighted heavily relative to tropism so the
search only sacrifices when it actually pays off.
"""

from __future__ import annotations

from typing import List

import chess

from ..common.evalutil import MATE, material, tapered_pst
from ..common.moveutil import pick_best
from ..timeman import TimeLimits

# Tunables.  Keep tropism modest next to material so it attacks, never donates.
PST_WEIGHT = 1.0
TROPISM_WEIGHT = {
    chess.PAWN: 1,
    chess.KNIGHT: 4,
    chess.BISHOP: 4,
    chess.ROOK: 5,
    chess.QUEEN: 8,
    chess.KING: 0,
}
RING_ATTACKER_BONUS = 12
CHECK_BONUS = 18
MAX_DEPTH = 3


class Beeline:
    name = "BEELINE"
    author = "B-Side Engines"

    def new_game(self) -> None:
        pass

    def choose_move(self, board: chess.Board, limits: TimeLimits) -> chess.Move:
        limit_depth = limits.depth or MAX_DEPTH
        best_move = next(iter(board.legal_moves))
        # Iterative deepening so we always have a complete shallow answer in hand.
        for depth in range(1, limit_depth + 1):
            scored = self._root_search(board, depth, limits)
            if scored is None:  # ran out of time mid-depth; keep the last result
                break
            best_move = pick_best(scored)
        return best_move

    def _root_search(self, board, depth, limits):
        # Full window per root move so the scored list is exact for pick_best.
        scored = []
        for move in board.legal_moves:
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
            return self._eval_stm(board)

        best = -MATE * 2
        for move in board.legal_moves:
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

    def _eval_stm(self, board: chess.Board) -> float:
        score = evaluate(board)
        return score if board.turn == chess.WHITE else -score


def evaluate(board: chess.Board) -> float:
    """Material + PST + king tropism, from White's point of view."""
    score = material(board) + PST_WEIGHT * tapered_pst(board)

    for color in (chess.WHITE, chess.BLACK):
        sign = 1 if color == chess.WHITE else -1
        enemy_king = board.king(not color)
        if enemy_king is None:
            continue
        for sq in _squares_of(board, color):
            piece = board.piece_at(sq)
            dist = _chebyshev(sq, enemy_king)
            score += sign * TROPISM_WEIGHT[piece.piece_type] * (7 - dist)
        score += sign * _ring_attackers_bonus(board, color, enemy_king)

    score += _check_bonus(board)
    return score


def _squares_of(board: chess.Board, color: chess.Color) -> List[int]:
    return list(chess.scan_forward(board.occupied_co[color]))


def _chebyshev(a: int, b: int) -> int:
    return chess.square_distance(a, b)


def _ring_attackers_bonus(board: chess.Board, color: chess.Color, enemy_king: int) -> int:
    """Credit each of ``color``'s pieces that attacks a square in the king's ring."""
    ring = _king_ring(enemy_king)
    count = 0
    for sq in ring:
        if board.attackers(color, sq):
            count += len(board.attackers(color, sq))
    return RING_ATTACKER_BONUS * count


def _king_ring(king_sq: int) -> List[int]:
    ring = [king_sq]
    kf, kr = chess.square_file(king_sq), chess.square_rank(king_sq)
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if df == 0 and dr == 0:
                continue
            f, r = kf + df, kr + dr
            if 0 <= f < 8 and 0 <= r < 8:
                ring.append(chess.square(f, r))
    return ring


def _check_bonus(board: chess.Board) -> int:
    """If the side to move is in check, that is bad for them (good for the giver)."""
    if board.is_check():
        return -CHECK_BONUS if board.turn == chess.WHITE else CHECK_BONUS
    return 0
