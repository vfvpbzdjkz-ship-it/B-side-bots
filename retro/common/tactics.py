"""Small tactical helpers shared by the engines.

These are deliberately cheap and approximate — enough to answer "is this capture
safe?" and "is that piece hanging?" without a search.
"""

from __future__ import annotations

from typing import Optional

import chess

from .evalutil import PIECE_VALUES


def mate_in_1(board: chess.Board) -> Optional[chess.Move]:
    """Return a move that delivers immediate checkmate, or ``None``."""
    for move in board.legal_moves:
        board.push(move)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return move
    return None


def is_hanging(board: chess.Board, square: int) -> bool:
    """True if the piece on ``square`` can be profitably won right now.

    A piece is "hanging" if it is attacked by the enemy and is either undefended,
    outnumbered by attackers, or attacked by something cheaper than itself.  Uses
    ``board.attackers`` and is intentionally approximate (it ignores pins, x-rays
    and the full exchange sequence).
    """
    piece = board.piece_at(square)
    if piece is None:
        return False

    own = piece.color
    attackers = board.attackers(not own, square)
    if not attackers:
        return False  # nobody is even hitting it

    defenders = board.attackers(own, square)
    if not defenders:
        return True  # attacked and wholly undefended -> free

    # Attacked and defended: it is loose if the attackers outnumber the defenders
    # or the cheapest attacker is worth less than the piece (a winning trade).
    if len(attackers) > len(defenders):
        return True
    cheapest_attacker = min(_value_at(board, sq) for sq in attackers)
    return cheapest_attacker < PIECE_VALUES[piece.piece_type]


def see_gain(board: chess.Board, move: chess.Move) -> int:
    """Approximate static exchange value of a capture, in centipawns.

    ``value(captured) - (value(mover) if the destination is defended by the
    opponent else 0)``.  This is **approximate** — it models a single recapture,
    not the full exchange sequence — but it is enough to ask "is this capture
    safe?".  Non-captures return ``0``.
    """
    captured = _captured_value(board, move)
    if captured == 0 and not board.is_en_passant(move):
        return 0  # not a capture

    mover = board.piece_at(move.from_square)
    mover_value = PIECE_VALUES[mover.piece_type] if mover else 0

    opponent = not board.turn
    defended = bool(board.attackers(opponent, move.to_square))
    return captured - (mover_value if defended else 0)


# --- internals ------------------------------------------------------------

def _captured_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return PIECE_VALUES[chess.PAWN]
    victim = board.piece_at(move.to_square)
    return PIECE_VALUES[victim.piece_type] if victim else 0


def _value_at(board: chess.Board, square: int) -> int:
    piece = board.piece_at(square)
    return PIECE_VALUES[piece.piece_type] if piece else 0
