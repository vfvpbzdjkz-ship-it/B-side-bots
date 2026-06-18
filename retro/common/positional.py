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
# Part 2 — piece placement.
W_SAFE_FROM_KICK = 15
W_CAN_BE_KICKED = -22
W_OUTPOST = 25
W_KNIGHT_RIM = -18
W_WITH_TEMPO = 12
W_EYE_CENTER = 6
# Part 3 — pawn structure & king safety.
W_DOUBLED = -12          # per extra doubled pawn we create
W_ISOLATED = -10         # per isolated pawn we create
W_CONNECTED = 6          # a pawn move that stays connected to its neighbours
W_ROOK_BEHIND_PASSER = 14
W_KING_SHIELD = -18      # pushing a pawn out of our castled king's shield

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

    # Part 3 needs our pawn structure *before* the move for comparison.
    if pt == chess.PAWN:
        doubled_before, isolated_before = _pawn_weakness(board, us)

    board.push(move)
    try:
        dest = move.to_square

        # --- Part 2: piece placement ------------------------------------
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

        # --- Part 3: pawn structure & king safety -----------------------
        if pt == chess.PAWN:
            doubled_after, isolated_after = _pawn_weakness(board, us)
            delta += W_DOUBLED * max(0, doubled_after - doubled_before)
            delta += W_ISOLATED * max(0, isolated_after - isolated_before)
            if doubled_after <= doubled_before and isolated_after <= isolated_before \
                    and _pawn_has_neighbour(board, dest, us):
                delta += W_CONNECTED
                reasons.append("pawns stay connected")
            if _breaks_king_shield(board, move, us):
                delta += W_KING_SHIELD

        if pt == chess.ROOK and _rook_behind_passer(board, dest, us):
            delta += W_ROOK_BEHIND_PASSER
            reasons.append("behind the passed pawn")
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


def _pawn_weakness(board: chess.Board, color: chess.Color) -> Tuple[int, int]:
    """Return (doubled count, isolated count) for ``color``'s pawns."""
    files = [0] * 8
    for sq in board.pieces(chess.PAWN, color):
        files[chess.square_file(sq)] += 1
    doubled = sum(max(0, c - 1) for c in files)
    isolated = 0
    for f in range(8):
        if files[f] == 0:
            continue
        left = files[f - 1] if f > 0 else 0
        right = files[f + 1] if f < 7 else 0
        if left == 0 and right == 0:
            isolated += files[f]
    return doubled, isolated


def _pawn_has_neighbour(board: chess.Board, square: int, us: chess.Color) -> bool:
    """True if a friendly pawn sits on an adjacent file (i.e. not isolated)."""
    f = chess.square_file(square)
    for af in (f - 1, f + 1):
        if not 0 <= af < 8:
            continue
        for r in range(8):
            piece = board.piece_at(chess.square(af, r))
            if piece is not None and piece.piece_type == chess.PAWN and piece.color == us:
                return True
    return False


def _breaks_king_shield(board: chess.Board, move: chess.Move, us: chess.Color) -> bool:
    """True if the move pushes a pawn out of a castled king's pawn shield."""
    king = board.king(us)
    if king is None:
        return False
    home = 0 if us == chess.WHITE else 7
    if chess.square_rank(king) != home:
        return False  # king isn't tucked on the back rank
    pawn_home = 1 if us == chess.WHITE else 6
    if chess.square_rank(move.from_square) != pawn_home:
        return False  # only the first push of a shield pawn counts
    king_file = chess.square_file(king)
    from_file = chess.square_file(move.from_square)
    if king_file >= 5 and from_file >= 5:
        return True   # kingside-castled, pushed an f/g/h pawn
    if king_file <= 2 and from_file <= 2:
        return True   # queenside-castled, pushed an a/b/c pawn
    return False


def _rook_behind_passer(board: chess.Board, square: int, us: chess.Color) -> bool:
    """True if a rook on ``square`` stands behind a friendly passed pawn on its file."""
    f = chess.square_file(square)
    r = chess.square_rank(square)
    for rr in range(8):
        psq = chess.square(f, rr)
        piece = board.piece_at(psq)
        if piece is None or piece.piece_type != chess.PAWN or piece.color != us:
            continue
        if not _is_passed(board, psq, us):
            continue
        if us == chess.WHITE and r < rr:
            return True
        if us == chess.BLACK and r > rr:
            return True
    return False


def _is_passed(board: chess.Board, square: int, color: chess.Color) -> bool:
    """A pawn is passed if no enemy pawn can stop it on its file or the adjacent ones."""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    enemy = not color
    for f in (file - 1, file, file + 1):
        if not 0 <= f < 8:
            continue
        for r in range(8):
            piece = board.piece_at(chess.square(f, r))
            if piece is None or piece.piece_type != chess.PAWN or piece.color != enemy:
                continue
            if color == chess.WHITE and r > rank:
                return False
            if color == chess.BLACK and r < rank:
                return False
    return True
