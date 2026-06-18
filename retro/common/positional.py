"""A positional refinement layer — book wisdom about *where* a piece belongs.

The maxims in COPYBOOK decide *what* to do ("develop a knight"); this module
refines *where*, the way a chess primer would: don't put a minor where a pawn can
kick it (you'd just lose the tempo back), prefer a protected outpost, keep knights
off the rim, and develop with tempo by hitting something.

``assess(board, move)`` returns ``(score_delta, reasons)``:

* ``score_delta`` is a centipawn adjustment added when ranking candidate moves, so
  the maxim picks the *best* square, not merely a legal one;
* ``reasons`` is a list of short human phrases for the move COPYBOOK actually
  plays, so the narration can explain itself ("develop a knight (safe from pawn
  kicks, to an outpost)").

Everything here is O(1)-ish per move (a handful of bitboard/attack queries), so it
stays a speedy, search-free engine.
"""

from __future__ import annotations

from typing import List, Tuple

import chess

from .evalutil import PIECE_VALUES

# Refinement weights (centipawns) — comparable in scale to PST deltas so they
# nudge square choice without overriding material or the base evaluation.
W_SAFE_FROM_KICK = 15
W_CAN_BE_KICKED = -22
W_OUTPOST = 25
W_KNIGHT_RIM = -18
W_WITH_TEMPO = 12
W_EYE_CENTER = 6

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
MINOR = (chess.KNIGHT, chess.BISHOP)


def assess(board: chess.Board, move: chess.Move) -> Tuple[float, List[str]]:
    """Return (centipawn refinement, reasons) for placing a piece via ``move``."""
    mover = board.piece_at(move.from_square)
    if mover is None:
        return 0.0, []
    us = board.turn
    enemy = not us
    pt = mover.piece_type

    delta = 0.0
    reasons: List[str] = []

    board.push(move)
    try:
        dest = move.to_square
        if pt in MINOR:
            kicked = _can_be_kicked(board, dest, us, enemy)
            if kicked:
                delta += W_CAN_BE_KICKED
            else:
                delta += W_SAFE_FROM_KICK
                reasons.append("safe from pawn kicks")
                if _defended_by_pawn(board, dest, us):
                    delta += W_OUTPOST
                    reasons.append("to an outpost")
            if pt == chess.KNIGHT and chess.square_file(dest) in (0, 7):
                delta += W_KNIGHT_RIM  # "a knight on the rim is dim"

        if _attacks_something_valuable(board, dest, us, enemy):
            delta += W_WITH_TEMPO
            reasons.append("with tempo")

        if _eyes_center(board, dest, us):
            delta += W_EYE_CENTER
            if pt in MINOR:
                reasons.append("eyeing the center")
    finally:
        board.pop()

    return delta, reasons


# --- helpers --------------------------------------------------------------

def _defended_by_pawn(board: chess.Board, square: int, us: chess.Color) -> bool:
    for sq in board.attackers(us, square):
        if board.piece_at(sq).piece_type == chess.PAWN:
            return True
    return False


def _can_be_kicked(board: chess.Board, square: int, us: chess.Color,
                   enemy: chess.Color) -> bool:
    """True if an enemy pawn attacks ``square`` now or can in a single push."""
    f, r = chess.square_file(square), chess.square_rank(square)
    # Squares an enemy pawn would have to stand on to attack ``square``.
    attacker_rank = r + 1 if us == chess.WHITE else r - 1
    if not 0 <= attacker_rank < 8:
        return False
    for af in (f - 1, f + 1):
        if not 0 <= af < 8:
            continue
        asq = chess.square(af, attacker_rank)
        piece = board.piece_at(asq)
        if piece is not None:
            if piece.piece_type == chess.PAWN and piece.color == enemy:
                return True  # already attacking it
            continue  # square occupied; no pawn can push onto it
        if _pawn_can_push_to(board, asq, enemy):
            return True  # a pawn can step there next move and kick us
    return False


def _pawn_can_push_to(board: chess.Board, target: int, color: chess.Color) -> bool:
    """Can a ``color`` pawn reach the (empty) ``target`` via a single or double push?"""
    tf, tr = chess.square_file(target), chess.square_rank(target)
    step = 1 if color == chess.WHITE else -1

    behind_rank = tr - step
    if 0 <= behind_rank < 8:
        src = chess.square(tf, behind_rank)
        p = board.piece_at(src)
        if p is not None and p.piece_type == chess.PAWN and p.color == color:
            return True

    # Double push from the pawn's home rank onto the 4th/5th rank.
    double_target_rank = 3 if color == chess.WHITE else 4
    home_rank = 1 if color == chess.WHITE else 6
    if tr == double_target_rank:
        src = chess.square(tf, home_rank)
        mid = chess.square(tf, home_rank + step)
        p = board.piece_at(src)
        if p is not None and p.piece_type == chess.PAWN and p.color == color \
                and board.piece_at(mid) is None:
            return True
    return False


def _attacks_something_valuable(board: chess.Board, square: int, us: chess.Color,
                                enemy: chess.Color) -> bool:
    """Does the piece on ``square`` now hit an enemy piece worth a minor or more?"""
    for target in board.attacks(square):
        piece = board.piece_at(target)
        if piece is not None and piece.color == enemy \
                and PIECE_VALUES[piece.piece_type] >= PIECE_VALUES[chess.KNIGHT]:
            return True
    return False


def _eyes_center(board: chess.Board, square: int, us: chess.Color) -> bool:
    if square in CENTER:
        return True
    return any(sq in CENTER for sq in board.attacks(square))
