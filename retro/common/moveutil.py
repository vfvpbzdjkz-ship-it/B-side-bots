"""Move-ordering helpers and the determinism-busting tiebreak.

``plausibility`` is SHANNSTEIN's cheap "is this move worth looking at?" score.
``pick_best`` is the shared "take the max, but break ties randomly" used by every
engine so a deterministic evaluator does not sleepwalk into threefold draws.
"""

from __future__ import annotations

import random
from typing import Iterable, List, Optional, Tuple

import chess

from .evalutil import PIECE_VALUES
from .tactics import see_gain

# The four classical central squares.
CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
# A wider "broad center" used for pawn-push credit.
BROAD_CENTER = CENTER | {chess.C4, chess.F4, chess.C5, chess.F5,
                         chess.D3, chess.E3, chess.D6, chess.E6}

ScoredMove = Tuple[chess.Move, float]


def pick_best(scored: Iterable[ScoredMove], tolerance: float = 1e-6) -> Optional[chess.Move]:
    """Return the highest-scoring move, breaking ties (within ``tolerance``) at random."""
    scored = list(scored)
    if not scored:
        return None
    best = max(score for _, score in scored)
    winners = [move for move, score in scored if score >= best - tolerance]
    return random.choice(winners)


def plausibility(board: chess.Board, move: chess.Move) -> float:
    """Cheap, additive "this move looks reasonable" score for forward pruning.

    Rewards checks, good captures, castling, developing a minor, central pawn
    pushes, promotions, and moves that hit or shore up a piece.  Cheap by design —
    a single push/pop is the most expensive thing it does.
    """
    mover = board.piece_at(move.from_square)
    if mover is None:
        return 0.0
    pt = mover.piece_type
    score = 0.0

    if board.gives_check(move):
        score += 50.0

    if board.is_capture(move):
        score += 40.0 + 0.5 * see_gain(board, move)

    if board.is_castling(move):
        score += 35.0
    elif pt in (chess.KNIGHT, chess.BISHOP) and _is_developing(board, move):
        score += 20.0

    if pt == chess.PAWN and move.to_square in CENTER:
        score += 15.0

    if move.promotion:
        score += 60.0

    score += _attack_defend_bonus(board, move)
    return score


# --- helpers --------------------------------------------------------------

def _home_rank(color: chess.Color) -> int:
    return 0 if color == chess.WHITE else 7


def _is_developing(board: chess.Board, move: chess.Move) -> bool:
    """A minor piece leaving its home rank toward the board is 'developing'."""
    mover = board.piece_at(move.from_square)
    if mover is None or mover.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return False
    return chess.square_rank(move.from_square) == _home_rank(mover.color)


def _attack_defend_bonus(board: chess.Board, move: chess.Move) -> float:
    """Small credit for landing on a square that hits enemies / shields friends."""
    bonus = 0.0
    board.push(move)
    try:
        # After the push it is the opponent's turn; the piece we just moved now
        # belongs to the side *not* to move.
        mover_color = not board.turn
        landed = move.to_square
        for target in board.attacks(landed):
            piece = board.piece_at(target)
            if piece is None:
                continue
            if piece.color != mover_color:
                # Hitting an enemy piece, scaled gently by what it is worth.
                bonus += 2.0 + 0.01 * PIECE_VALUES[piece.piece_type]
            else:
                # Defending a friendly piece.
                bonus += 1.0
    finally:
        board.pop()
    return bonus


def open_file_score(board: chess.Board, file_index: int, color: chess.Color) -> int:
    """0 = blocked by our own pawn, 1 = half-open (only enemy pawn), 2 = fully open."""
    own_pawn = enemy_pawn = False
    for rank in range(8):
        piece = board.piece_at(chess.square(file_index, rank))
        if piece is None or piece.piece_type != chess.PAWN:
            continue
        if piece.color == color:
            own_pawn = True
        else:
            enemy_pawn = True
    if own_pawn:
        return 0
    return 2 if not enemy_pawn else 1
