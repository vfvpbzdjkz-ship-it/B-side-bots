"""COPYBOOK — a symbolic rule-based expert system (1950s-60s flavour).

A prioritized cascade of if-then maxims.  Each rule looks at the board and either
returns a move or passes to the next rule.  There is no search tree at all — just
principles, applied in order, each candidate vetted by a sharp 1-ply safety filter
and ranked by a static positional judgement.

The "book" is deliberately strong for a search-less engine:

* the **safety veto** rejects any move that hangs material *anywhere* (not just the
  piece that moved) or that walks into mate-in-1 — so COPYBOOK rarely blunders;
* within every maxim, candidates are ranked by a one-ply positional evaluation
  (the shared PeSTO eval), so it picks the *best* developing move, the *best*
  central break, the *best* quiet move — not merely the first legal one;
* the final fallback is a full KNEEJERK-grade "play the best safe move" pass.

It narrates which rule fired (``info string rule 6: develop a knight``); that
self-explanation is the demo charm.
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

import chess

from ..common.evalutil import MG_PST, EG_PST, evaluate, game_phase, phase_weights
from ..common.moveutil import open_file_score
from ..common.openings import book_move
from ..common.tactics import is_hanging, mate_in_1, see_gain
from ..timeman import TimeLimits

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
# Below this remaining-material phase we are "in the endgame" and switch on the
# endgame maxims (push passed pawns, march the king up).
ENDGAME_PHASE = 8
Candidate = Tuple[chess.Move, str]


class Copybook:
    name = "COPYBOOK"
    author = "B-Side Engines"

    def __init__(self) -> None:
        self.narration = ""
        self._rules = [
            self._rule_mate,             # 1
            self._rule_escape_check,     # 2
            self._rule_safe_capture,     # 3
            self._rule_save_hanging,     # 4
            self._rule_castle,           # 5
            self._rule_develop_minor,    # 6
            self._rule_center_pawn,      # 7
            self._rule_rook_open_file,   # 8
            self._rule_push_passed_pawn,  # 9  (endgame)
            self._rule_activate_king,     # 10 (endgame)
            self._rule_improve_worst,     # 11
            self._rule_waiting,           # 12
        ]

    def new_game(self) -> None:
        self.narration = ""

    def choose_move(self, board: chess.Board, limits: TimeLimits) -> chess.Move:
        # First, play "by the book": if the position is still known opening theory,
        # follow it and name the opening.
        booked = book_move(board)
        if booked is not None:
            move, opening = booked
            self.narration = f"book: {opening}"
            return move

        # Out of book — fall back to the cascade of chess-primer maxims.
        for number, rule in enumerate(self._rules, start=1):
            result = rule(board)
            if result is not None:
                move, description = result
                self.narration = f"rule {number}: {description}"
                return move
        # Should be unreachable (the waiting rule always finds something), but stay safe.
        move = random.choice(list(board.legal_moves))
        self.narration = "rule 12: safe waiting move"
        return move

    # --- rule 1 -----------------------------------------------------------
    def _rule_mate(self, board) -> Optional[Candidate]:
        move = mate_in_1(board)
        if move is not None:
            return move, "deliver mate"
        return None

    # --- rule 2 -----------------------------------------------------------
    def _rule_escape_check(self, board) -> Optional[Candidate]:
        if not board.is_check():
            return None
        # We must move; prefer a safe evasion, and among those the one that leaves
        # us best placed.  If nothing is "safe" we still have to play *something*.
        legal = list(board.legal_moves)
        safe = [m for m in legal if self._safe(board, m)]
        pool = safe or legal
        best = max(pool, key=lambda m: self._score_move(board, m))
        return best, "escape check safely"

    # --- rule 3 -----------------------------------------------------------
    def _rule_safe_capture(self, board) -> Optional[Candidate]:
        best_move = None
        best_key = (-1, 0.0)
        for move in board.legal_moves:
            if not board.is_capture(move):
                continue
            gain = see_gain(board, move)
            if gain < 0 or not self._safe(board, move):
                continue
            # Win the most material; break ties by how good the position looks.
            key = (gain, self._score_move(board, move))
            if key > best_key:
                best_key, best_move = key, move
        if best_move is not None:
            return best_move, "win material with a safe capture"
        return None

    # --- rule 4 -----------------------------------------------------------
    def _rule_save_hanging(self, board) -> Optional[Candidate]:
        us = board.turn
        hanging = [sq for sq in chess.scan_forward(board.occupied_co[us])
                   if is_hanging(board, sq)]
        if not hanging:
            return None
        # Rescue the most valuable hanging piece first.
        hanging.sort(key=lambda sq: _piece_value(board, sq), reverse=True)
        for sq in hanging:
            # (a) the best safe move of the piece to a square where it is safe.
            rescues = []
            for move in board.legal_moves:
                if move.from_square != sq or not self._safe(board, move):
                    continue
                board.push(move)
                rescued = not is_hanging(board, move.to_square)
                board.pop()
                if rescued:
                    rescues.append(move)
            if rescues:
                best = max(rescues, key=lambda m: self._score_move(board, m))
                return best, "save a hanging piece"
            # (b) otherwise the best safe move that adds a defender.
            defends = []
            for move in board.legal_moves:
                if move.from_square == sq or not self._safe(board, move):
                    continue
                board.push(move)
                rescued = not is_hanging(board, sq)
                board.pop()
                if rescued:
                    defends.append(move)
            if defends:
                best = max(defends, key=lambda m: self._score_move(board, m))
                return best, "defend a hanging piece"
        return None

    # --- rule 5 -----------------------------------------------------------
    def _rule_castle(self, board) -> Optional[Candidate]:
        us = board.turn
        king_home = chess.E1 if us == chess.WHITE else chess.E8
        if board.king(us) != king_home:
            return None  # already moved / castled
        castles = [m for m in board.legal_moves
                   if board.is_castling(m) and not self._allows_mate(board, m)]
        if castles:
            best = max(castles, key=lambda m: self._score_move(board, m))
            return best, "castle to safety"
        return None

    # --- rule 6 -----------------------------------------------------------
    def _rule_develop_minor(self, board) -> Optional[Candidate]:
        us = board.turn
        home = 0 if us == chess.WHITE else 7
        # Knights before bishops.
        for piece_type, label in ((chess.KNIGHT, "develop a knight"),
                                  (chess.BISHOP, "develop a bishop")):
            candidates = []
            for move in board.legal_moves:
                mover = board.piece_at(move.from_square)
                if mover is None or mover.piece_type != piece_type:
                    continue
                if chess.square_rank(move.from_square) != home:
                    continue  # only count leaving the back rank as development
                if not self._safe(board, move):
                    continue
                candidates.append(move)
            if candidates:
                best = max(candidates, key=lambda m: self._score_move(board, m))
                return best, label
        return None

    # --- rule 7 -----------------------------------------------------------
    def _rule_center_pawn(self, board) -> Optional[Candidate]:
        candidates = []
        for move in board.legal_moves:
            mover = board.piece_at(move.from_square)
            if mover is None or mover.piece_type != chess.PAWN:
                continue
            if move.to_square in CENTER and self._safe(board, move):
                candidates.append(move)
        if candidates:
            best = max(candidates, key=lambda m: self._score_move(board, m))
            return best, "stake a center pawn"
        return None

    # --- rule 8 -----------------------------------------------------------
    def _rule_rook_open_file(self, board) -> Optional[Candidate]:
        us = board.turn
        best = None
        best_key = (0, 0.0)
        for move in board.legal_moves:
            mover = board.piece_at(move.from_square)
            if mover is None or mover.piece_type != chess.ROOK:
                continue
            if not self._safe(board, move):
                continue
            openness = open_file_score(board, chess.square_file(move.to_square), us)
            if openness <= 0:
                continue
            key = (openness, self._score_move(board, move))
            if key > best_key:
                best_key, best = key, move
        if best is not None:
            return best, "put a rook on an open file"
        return None

    # --- rule 9 (endgame) -------------------------------------------------
    def _rule_push_passed_pawn(self, board) -> Optional[Candidate]:
        if game_phase(board) > ENDGAME_PHASE:
            return None
        us = board.turn
        candidates = []
        for move in board.legal_moves:
            mover = board.piece_at(move.from_square)
            if mover is None or mover.piece_type != chess.PAWN:
                continue
            if not _is_passed(board, move.from_square, us):
                continue
            # A forward push of a passed pawn (not a capture sideways).
            if chess.square_file(move.from_square) != chess.square_file(move.to_square):
                continue
            if self._safe(board, move):
                candidates.append(move)
        if candidates:
            best = max(candidates, key=lambda m: self._score_move(board, m))
            return best, "push a passed pawn"
        return None

    # --- rule 10 (endgame) ------------------------------------------------
    def _rule_activate_king(self, board) -> Optional[Candidate]:
        if game_phase(board) > ENDGAME_PHASE:
            return None
        us = board.turn
        king_sq = board.king(us)
        current = _piece_pst(board, king_sq)
        improving = []
        for move in board.legal_moves:
            if move.from_square != king_sq or not self._safe(board, move):
                continue
            board.push(move)
            placed = _piece_pst(board, move.to_square)
            board.pop()
            if placed > current:  # the king steps toward the centre / the action
                improving.append(move)
        if improving:
            best = max(improving, key=lambda m: self._score_move(board, m))
            return best, "centralize the king"
        return None

    # --- rule 11 ----------------------------------------------------------
    def _rule_improve_worst(self, board) -> Optional[Candidate]:
        us = board.turn
        squares = [sq for sq in chess.scan_forward(board.occupied_co[us])
                   if board.piece_at(sq).piece_type != chess.KING]
        if not squares:
            return None
        # The worst-placed piece is the one with the lowest positional value.
        squares.sort(key=lambda sq: _piece_pst(board, sq))
        for sq in squares:
            current = _piece_pst(board, sq)
            improving = []
            for move in board.legal_moves:
                if move.from_square != sq or not self._safe(board, move):
                    continue
                board.push(move)
                placed = _piece_pst(board, move.to_square)
                board.pop()
                if placed > current:
                    improving.append(move)
            if improving:
                best = max(improving, key=lambda m: self._score_move(board, m))
                return best, "improve the worst-placed piece"
        return None

    # --- rule 12 ----------------------------------------------------------
    def _rule_waiting(self, board) -> Optional[Candidate]:
        legal = list(board.legal_moves)
        if not legal:
            return None
        safe = [m for m in legal if self._safe(board, m)]
        pool = safe or legal
        # KNEEJERK-grade fallback: play the best-looking safe move.
        best = max(pool, key=lambda m: self._score_move(board, m))
        return best, "safe waiting move"

    # --- safety filter ----------------------------------------------------
    def _safe(self, board: chess.Board, move: chess.Move) -> bool:
        """1-ply veto: do not hang material anywhere, do not allow mate-in-1."""
        return not self._allows_mate(board, move) and not self._loses_material(board, move)

    @staticmethod
    def _allows_mate(board: chess.Board, move: chess.Move) -> bool:
        board.push(move)
        try:
            return mate_in_1(board) is not None
        finally:
            board.pop()

    @staticmethod
    def _loses_material(board: chess.Board, move: chess.Move) -> bool:
        """True if, after this move, the opponent has a capture that wins material.

        This is the heart of the improved book: it looks at *every* enemy capture
        reply (approximate SEE), so it catches leaving any piece loose — including
        pieces other than the one that just moved, and squares vacated behind it.
        """
        board.push(move)
        try:
            worst = 0
            for reply in board.legal_moves:
                if board.is_capture(reply):
                    gain = see_gain(board, reply)
                    if gain > worst:
                        worst = gain
            return worst > 0
        finally:
            board.pop()

    def _score_move(self, board: chess.Board, move: chess.Move) -> float:
        """Static value to us after playing ``move`` (the shared PeSTO eval)."""
        sign = 1.0 if board.turn == chess.WHITE else -1.0
        board.push(move)
        try:
            return sign * evaluate(board)
        finally:
            board.pop()


# --- module helpers -------------------------------------------------------

def _piece_value(board: chess.Board, square: int) -> int:
    from ..common.evalutil import PIECE_VALUES
    piece = board.piece_at(square)
    return PIECE_VALUES[piece.piece_type] if piece else 0


def _piece_pst(board: chess.Board, square: int) -> float:
    """How well a single piece is placed (its own tapered positional value)."""
    piece = board.piece_at(square)
    if piece is None:
        return 0.0
    mg_w, eg_w = phase_weights(board)
    pt = piece.piece_type
    idx = chess.square_mirror(square) if piece.color == chess.WHITE else square
    return mg_w * MG_PST[pt][idx] + eg_w * EG_PST[pt][idx]


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
