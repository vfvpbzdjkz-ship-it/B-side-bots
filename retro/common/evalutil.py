"""Material values and a tapered piece-square evaluation (PeSTO tables).

Centipawn scores are always returned **from White's point of view** by
:func:`evaluate`; :func:`eval_stm` flips to the side to move (what negamax wants).

The piece-square component uses the public-domain **PeSTO** middlegame/endgame
tables (Ronald Friederich / RofChade).  The published tables bake a per-piece
base value into every square; we subtract that base out so the tables are *purely
positional* and the material term below (``PIECE_VALUES``) is the single source of
truth for material.  Game phase is interpolated from remaining material so the eval
slides smoothly from middlegame to endgame.
"""

from __future__ import annotations

import chess

# --- Material -------------------------------------------------------------

# The canonical "100 / 320 / 330 / 500 / 900" set.  Used here and by tactics.py,
# beeline's material term, and copybook's safety checks.
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,  # the king's "value" is handled by mate scoring, not material
}

MATE = 1_000_000  # large enough to dwarf any material swing

# --- Game phase -----------------------------------------------------------

# Phase weights per remaining piece (both colors), capped at 24 = full material.
_PHASE_WEIGHT = {
    chess.KNIGHT: 1,
    chess.BISHOP: 1,
    chess.ROOK: 2,
    chess.QUEEN: 4,
}
PHASE_MAX = 24

# --- PeSTO piece-square tables --------------------------------------------
# Tables are written rank 8 first (index 0 == a8).  A White piece on ``sq``
# (a1 == 0) reads ``table[chess.square_mirror(sq)]``; a Black piece reads
# ``table[sq]`` and is negated.  Base material (below) is subtracted at import so
# what remains is positional only.

_MG_PAWN = [
    0, 0, 0, 0, 0, 0, 0, 0,
    98, 134, 61, 95, 68, 126, 34, -11,
    -6, 7, 26, 31, 65, 56, 25, -20,
    -14, 13, 6, 21, 23, 12, 17, -23,
    -27, -2, -5, 12, 17, 6, 10, -25,
    -26, -4, -4, -10, 3, 3, 33, -12,
    -35, -1, -20, -23, -15, 24, 38, -22,
    0, 0, 0, 0, 0, 0, 0, 0,
]
_EG_PAWN = [
    0, 0, 0, 0, 0, 0, 0, 0,
    178, 173, 158, 134, 147, 132, 165, 187,
    94, 100, 85, 67, 56, 53, 82, 84,
    32, 24, 13, 5, -2, 4, 17, 17,
    13, 9, -3, -7, -7, -8, 3, -1,
    4, 7, -6, 1, 0, -5, -1, -8,
    13, 8, 8, 10, 13, 0, 2, -7,
    0, 0, 0, 0, 0, 0, 0, 0,
]
_MG_KNIGHT = [
    -167, -89, -34, -49, 61, -97, -15, -107,
    -73, -41, 72, 36, 23, 62, 7, -17,
    -47, 60, 37, 65, 84, 129, 73, 44,
    -9, 17, 19, 53, 37, 69, 18, 22,
    -13, 4, 16, 13, 28, 19, 21, -8,
    -23, -9, 12, 10, 19, 17, 25, -16,
    -29, -53, -12, -3, -1, 18, -14, -19,
    -105, -21, -58, -33, -17, -28, -19, -23,
]
_EG_KNIGHT = [
    -58, -38, -13, -28, -31, -27, -63, -99,
    -25, -8, -25, -2, -9, -25, -24, -52,
    -24, -20, 10, 9, -1, -9, -19, -41,
    -17, 3, 22, 22, 22, 11, 8, -18,
    -18, -6, 16, 25, 16, 17, 4, -18,
    -23, -3, -1, 15, 10, -3, -20, -22,
    -42, -20, -10, -5, -2, -20, -23, -44,
    -29, -51, -23, -15, -22, -18, -50, -64,
]
_MG_BISHOP = [
    -29, 4, -82, -37, -25, -42, 7, -8,
    -26, 16, -18, -13, 30, 59, 18, -47,
    -16, 37, 43, 40, 35, 50, 37, -2,
    -4, 5, 19, 50, 37, 37, 7, -2,
    -6, 13, 13, 26, 34, 12, 10, 4,
    0, 15, 15, 15, 14, 27, 18, 10,
    4, 15, 16, 0, 7, 21, 33, 1,
    -33, -3, -14, -21, -13, -12, -39, -21,
]
_EG_BISHOP = [
    -14, -21, -11, -8, -7, -9, -17, -24,
    -8, -4, 7, -12, -3, -13, -4, -14,
    2, -8, 0, -1, -2, 6, 0, 4,
    -3, 9, 12, 9, 14, 10, 3, 2,
    -6, 3, 13, 19, 7, 10, -3, -9,
    -12, -3, 8, 10, 13, 3, -7, -15,
    -14, -18, -7, -1, 4, -9, -15, -27,
    -23, -9, -23, -5, -9, -16, -5, -17,
]
_MG_ROOK = [
    32, 42, 32, 51, 63, 9, 31, 43,
    27, 32, 58, 62, 80, 67, 26, 44,
    -5, 19, 26, 36, 17, 45, 61, 16,
    -24, -11, 7, 26, 24, 35, -8, -20,
    -36, -26, -12, -1, 9, -7, 6, -23,
    -45, -25, -16, -17, 3, 0, -5, -33,
    -44, -16, -20, -9, -1, 11, -6, -71,
    -19, -13, 1, 17, 16, 7, -37, -26,
]
_EG_ROOK = [
    13, 10, 18, 15, 12, 12, 8, 5,
    11, 13, 13, 11, -3, 3, 8, 3,
    7, 7, 7, 5, 4, -3, -5, -3,
    4, 3, 13, 1, 2, 1, -1, 2,
    3, 5, 8, 4, -5, -6, -8, -11,
    -4, 0, -5, -1, -7, -12, -8, -16,
    -6, -6, 0, 2, -9, -9, -11, -3,
    -9, 2, 3, -1, -5, -13, 4, -20,
]
_MG_QUEEN = [
    -28, 0, 29, 12, 59, 44, 43, 45,
    -24, -39, -5, 1, -16, 57, 28, 54,
    -13, -17, 7, 8, 29, 56, 47, 57,
    -27, -27, -16, -16, -1, 17, -2, 1,
    -9, -26, -9, -10, -2, -4, 3, -3,
    -14, 2, -11, -2, -5, 2, 14, 5,
    -35, -8, 11, 2, 8, 15, -3, 1,
    -1, -18, -9, 10, -15, -25, -31, -50,
]
_EG_QUEEN = [
    -9, 22, 22, 27, 27, 19, 10, 20,
    -17, 20, 32, 41, 58, 25, 30, 0,
    -20, 6, 9, 49, 47, 35, 19, 9,
    3, 22, 24, 45, 57, 40, 57, 36,
    -18, 28, 19, 47, 31, 34, 39, 23,
    -16, -27, 15, 6, 9, 17, 10, 5,
    -22, -23, -30, -16, -16, -23, -36, -32,
    -33, -28, -22, -43, -5, -32, -20, -41,
]
_MG_KING = [
    -65, 23, 16, -15, -56, -34, 2, 13,
    29, -1, -20, -7, -8, -4, -38, -29,
    -9, 24, 2, -16, -20, 6, 22, -22,
    -17, -20, -12, -27, -30, -25, -14, -36,
    -49, -1, -27, -39, -46, -44, -33, -51,
    -14, -14, -22, -46, -44, -30, -15, -27,
    1, 7, -8, -64, -43, -16, 9, 8,
    -15, 36, 12, -54, 8, -28, 24, 14,
]
_EG_KING = [
    -74, -35, -18, -18, -11, 15, 4, -17,
    -12, 17, 14, 17, 17, 38, 23, 11,
    10, 17, 23, 15, 20, 45, 44, 13,
    -8, 22, 24, 27, 26, 33, 26, 3,
    -18, -4, 21, 24, 27, 23, 9, -11,
    -19, -3, 11, 21, 23, 16, 7, -9,
    -27, -11, 4, 13, 14, 4, -5, -17,
    -53, -34, -21, -11, -28, -14, -24, -43,
]

_RAW_MG = {
    chess.PAWN: _MG_PAWN, chess.KNIGHT: _MG_KNIGHT, chess.BISHOP: _MG_BISHOP,
    chess.ROOK: _MG_ROOK, chess.QUEEN: _MG_QUEEN, chess.KING: _MG_KING,
}
_RAW_EG = {
    chess.PAWN: _EG_PAWN, chess.KNIGHT: _EG_KNIGHT, chess.BISHOP: _EG_BISHOP,
    chess.ROOK: _EG_ROOK, chess.QUEEN: _EG_QUEEN, chess.KING: _EG_KING,
}


# The tables above are the *positional* PeSTO tables: small per-square deltas with
# no material baked in (PeSTO applies its base material separately).  We supply our
# own material via PIECE_VALUES, so the tables are used as-is.
MG_PST = dict(_RAW_MG)
EG_PST = dict(_RAW_EG)


# --- Public API -----------------------------------------------------------

def game_phase(board: chess.Board) -> int:
    """Remaining-material phase, ``N*1 + B*1 + R*2 + Q*4`` capped at 24."""
    phase = 0
    for pt, weight in _PHASE_WEIGHT.items():
        phase += weight * (len(board.pieces(pt, chess.WHITE))
                           + len(board.pieces(pt, chess.BLACK)))
    return min(phase, PHASE_MAX)


def phase_weights(board: chess.Board):
    """Return ``(mg_weight, eg_weight)`` summing to 1.0."""
    mg_w = game_phase(board) / PHASE_MAX
    return mg_w, 1.0 - mg_w


def material(board: chess.Board) -> int:
    """Material balance in centipawns, from White's point of view."""
    total = 0
    for pt, value in PIECE_VALUES.items():
        if value == 0:
            continue
        total += value * len(board.pieces(pt, chess.WHITE))
        total -= value * len(board.pieces(pt, chess.BLACK))
    return total


def tapered_pst(board: chess.Board) -> float:
    """Tapered positional piece-square score (no material), White's view."""
    mg = 0
    eg = 0
    for sq in chess.scan_forward(board.occupied):
        piece = board.piece_at(sq)
        pt = piece.piece_type
        if piece.color == chess.WHITE:
            idx = chess.square_mirror(sq)
            mg += MG_PST[pt][idx]
            eg += EG_PST[pt][idx]
        else:
            mg -= MG_PST[pt][sq]
            eg -= EG_PST[pt][sq]
    mg_w, eg_w = phase_weights(board)
    return mg_w * mg + eg_w * eg


def evaluate(board: chess.Board) -> float:
    """Full static eval (material + tapered PST) in centipawns, White's view.

    Terminal positions are scored directly: checkmate is ``-MATE`` for the side to
    move (so ``+MATE`` for the mating side once flipped), draws are ``0``.
    """
    if board.is_checkmate():
        # Side to move has been mated -> very bad for them; sign by whose move.
        return -MATE if board.turn == chess.WHITE else MATE
    if board.is_stalemate() or board.is_insufficient_material() \
            or board.is_seventyfive_moves() or board.is_fivefold_repetition():
        return 0
    return material(board) + tapered_pst(board)


def eval_stm(board: chess.Board) -> float:
    """Static eval from the **side to move's** point of view (negamax convention)."""
    score = evaluate(board)
    return score if board.turn == chess.WHITE else -score
