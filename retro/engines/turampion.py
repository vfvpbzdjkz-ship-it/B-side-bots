"""TURAMPION — a Turochamp homage (Turing & Champernowne, 1948).

A point-count evaluation scored after a "dead-position" search: rather than
stopping at a fixed depth, keep following captures, recaptures and (briefly)
checks until the position is quiet, then score it — proto-quiescence, decades
early.  A 1-ply full-width layer looks at every reply once before going "dead",
which is closer to the original.

The evaluation is Turing-flavoured: material, mobility (sum of sqrt of each
piece's move count), piece safety, king safety, castling, pawn advancement, and
check/mate threats.
"""

from __future__ import annotations

import math
from typing import List

import chess

from ..common.evalutil import MATE, PIECE_VALUES, material
from ..common.moveutil import pick_best
from ..timeman import TimeLimits

INF = MATE * 2

# How deep the quiescence ("dead") search may follow forcing moves, and how many
# of those plies may still include checks (to avoid perpetual-check explosions).
QUIESCENCE_CAP = 8
CHECK_PLIES = 2

# Evaluation weights (all tunable, Turing-flavoured).
MOBILITY_WEIGHT = 2.0
SAFETY_BONUS = 6.0
KING_SAFETY_WEIGHT = 8.0
CASTLE_BONUS = 40.0
CASTLE_RIGHT_BONUS = 12.0
PAWN_ADVANCE_WEIGHT = 4.0
CHECK_THREAT_BONUS = 18.0


class Turampion:
    name = "TURAMPION"
    author = "B-Side Engines"

    def new_game(self) -> None:
        pass

    def choose_move(self, board: chess.Board, limits: TimeLimits) -> chess.Move:
        # 1-ply full-width layer, then a dead-position search of every reply.
        # Each root move is searched with a *full* window so the scored list is
        # exact (a narrow window would cap losing moves at the alpha bound and
        # corrupt the random tiebreak in pick_best).
        scored = []
        for move in board.legal_moves:
            board.push(move)
            val = -self._dead_search(board, -INF, INF, 0, limits)
            board.pop()
            scored.append((move, val))
            if limits.time_up():
                break
        if not scored:  # no legal moves; harness handles game-over
            return next(iter(board.legal_moves))
        return pick_best(scored)

    def _dead_search(self, board, alpha, beta, ply, limits) -> float:
        """Follow only 'considerable' moves until the position is quiet."""
        if board.is_checkmate():
            return -MATE + ply  # prefer faster mates
        if board.is_game_over():
            return 0.0

        stand = eval_stm(board)
        if stand >= beta:
            return beta
        if stand > alpha:
            alpha = stand

        if ply >= QUIESCENCE_CAP or limits.time_up():
            return alpha

        for move in self._considerable_moves(board, ply):
            board.push(move)
            val = -self._dead_search(board, -beta, -alpha, ply + 1, limits)
            board.pop()
            if val >= beta:
                return beta
            if val > alpha:
                alpha = val
            if limits.time_up():
                break
        return alpha

    @staticmethod
    def _considerable_moves(board: chess.Board, ply: int) -> List[chess.Move]:
        """Captures and recaptures always; checks only in the first few plies."""
        moves = list(board.generate_legal_captures())
        if ply < CHECK_PLIES:
            seen = set(moves)
            for move in board.legal_moves:
                if move not in seen and board.gives_check(move):
                    moves.append(move)
        return moves


def eval_stm(board: chess.Board) -> float:
    """Turochamp eval from the side-to-move's point of view (negamax convention)."""
    score = evaluate(board)
    return score if board.turn == chess.WHITE else -score


def evaluate(board: chess.Board) -> float:
    """Turochamp-flavoured point-count evaluation, from White's point of view."""
    if board.is_checkmate():
        return -MATE if board.turn == chess.WHITE else MATE
    if board.is_game_over():
        return 0.0

    score = float(material(board))
    score += _mobility(board, chess.WHITE) - _mobility(board, chess.BLACK)
    score += _piece_safety(board, chess.WHITE) - _piece_safety(board, chess.BLACK)
    score -= KING_SAFETY_WEIGHT * (_king_danger(board, chess.WHITE)
                                   - _king_danger(board, chess.BLACK))
    score += _castle_term(board, chess.WHITE) - _castle_term(board, chess.BLACK)
    score += _pawn_advance(board, chess.WHITE) - _pawn_advance(board, chess.BLACK)
    score += _check_threat(board)
    return score


def _mobility(board: chess.Board, color: chess.Color) -> float:
    """Sum over pieces of sqrt(number of squares it can move to) — Turing's idea."""
    total = 0.0
    own = board.occupied_co[color]
    for sq in chess.scan_forward(own):
        piece = board.piece_at(sq)
        if piece.piece_type == chess.KING:
            continue
        # Squares attacked that are not blocked by our own men (rough mobility).
        targets = int(board.attacks(sq)) & ~own
        total += math.sqrt(chess.popcount(targets))
    return MOBILITY_WEIGHT * total


def _piece_safety(board: chess.Board, color: chess.Color) -> float:
    """Small bonus for each of our pieces that is defended."""
    bonus = 0.0
    own = board.occupied_co[color]
    for sq in chess.scan_forward(own):
        if board.piece_at(sq).piece_type == chess.KING:
            continue
        if board.attackers(color, sq):
            bonus += SAFETY_BONUS
    return bonus


def _king_danger(board: chess.Board, color: chess.Color) -> float:
    """Penalty scaling with how many king-ring squares the enemy attacks."""
    king_sq = board.king(color)
    if king_sq is None:
        return 0.0
    danger = 0
    kf, kr = chess.square_file(king_sq), chess.square_rank(king_sq)
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            f, r = kf + df, kr + dr
            if 0 <= f < 8 and 0 <= r < 8:
                if board.attackers(not color, chess.square(f, r)):
                    danger += 1
    return float(danger)


def _castle_term(board: chess.Board, color: chess.Color) -> float:
    """Bonus for having castled (king tucked on g/c file) or retaining the right."""
    king_sq = board.king(color)
    if king_sq is None:
        return 0.0
    back_rank = 0 if color == chess.WHITE else 7
    castled_files = {chess.square_file(chess.G1), chess.square_file(chess.C1)}
    score = 0.0
    if chess.square_rank(king_sq) == back_rank \
            and chess.square_file(king_sq) in castled_files:
        score += CASTLE_BONUS
    if board.has_kingside_castling_rights(color) \
            or board.has_queenside_castling_rights(color):
        score += CASTLE_RIGHT_BONUS
    return score


def _pawn_advance(board: chess.Board, color: chess.Color) -> float:
    """Bonus by rank for advanced pawns."""
    bonus = 0.0
    for sq in board.pieces(chess.PAWN, color):
        rank = chess.square_rank(sq)
        advanced = rank if color == chess.WHITE else (7 - rank)
        bonus += PAWN_ADVANCE_WEIGHT * advanced
    return bonus


def _check_threat(board: chess.Board) -> float:
    """Bonus for the side currently giving check."""
    if board.is_check():
        return -CHECK_THREAT_BONUS if board.turn == chess.WHITE else CHECK_THREAT_BONUS
    return 0.0
