"""COPYBOOK — a symbolic rule-based expert system (1950s-60s flavour).

A prioritized cascade of if-then maxims.  Each rule looks at the board and either
returns a move or passes to the next rule.  There is no search tree at all — just
principles, applied in order, each candidate vetted by a 1-ply safety filter.

It narrates which rule fired (``info string rule 6: develop a knight``); that
self-explanation is the demo charm.
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

import chess

from ..common.evalutil import MG_PST, EG_PST, phase_weights
from ..common.moveutil import open_file_score
from ..common.tactics import is_hanging, mate_in_1, see_gain
from ..timeman import TimeLimits

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
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
            self._rule_improve_worst,    # 9
            self._rule_waiting,          # 10
        ]

    def new_game(self) -> None:
        self.narration = ""

    def choose_move(self, board: chess.Board, limits: TimeLimits) -> chess.Move:
        for number, rule in enumerate(self._rules, start=1):
            result = rule(board)
            if result is not None:
                move, description = result
                self.narration = f"rule {number}: {description}"
                return move
        # Should be unreachable (rule 10 always finds something), but stay safe.
        move = random.choice(list(board.legal_moves))
        self.narration = "rule 10: safe waiting move"
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
        # We must move; prefer an evasion that neither hangs material nor walks
        # into a mate, and break remaining ties by piece placement.
        legal = list(board.legal_moves)
        safe = [m for m in legal if self._safe(board, m)]
        pool = safe or legal
        best = max(pool, key=lambda m: self._move_pst_gain(board, m))
        return best, "escape check safely"

    # --- rule 3 -----------------------------------------------------------
    def _rule_safe_capture(self, board) -> Optional[Candidate]:
        best_move = None
        best_gain = -1
        for move in board.legal_moves:
            if not board.is_capture(move):
                continue
            gain = see_gain(board, move)
            if gain < 0:
                continue
            if not self._allows_mate(board, move) and gain > best_gain:
                best_gain, best_move = gain, move
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
            # (a) move it to a square where it is no longer hanging.
            for move in board.legal_moves:
                if move.from_square != sq or not self._safe(board, move):
                    continue
                board.push(move)
                rescued = not is_hanging(board, move.to_square)
                board.pop()
                if rescued:
                    return move, "save a hanging piece"
            # (b) otherwise add a defender so it is no longer hanging.
            for move in board.legal_moves:
                if move.from_square == sq or not self._safe(board, move):
                    continue
                board.push(move)
                rescued = not is_hanging(board, sq)
                board.pop()
                if rescued:
                    return move, "defend a hanging piece"
        return None

    # --- rule 5 -----------------------------------------------------------
    def _rule_castle(self, board) -> Optional[Candidate]:
        us = board.turn
        king_home = chess.E1 if us == chess.WHITE else chess.E8
        if board.king(us) != king_home:
            return None  # already moved / castled
        for move in board.legal_moves:
            if board.is_castling(move) and not self._allows_mate(board, move):
                return move, "castle to safety"
        return None

    # --- rule 6 -----------------------------------------------------------
    def _rule_develop_minor(self, board) -> Optional[Candidate]:
        us = board.turn
        home = 0 if us == chess.WHITE else 7
        # Knights before bishops.
        for piece_type, label in ((chess.KNIGHT, "develop a knight"),
                                  (chess.BISHOP, "develop a bishop")):
            best = None
            best_gain = -1e9
            for move in board.legal_moves:
                mover = board.piece_at(move.from_square)
                if mover is None or mover.piece_type != piece_type:
                    continue
                if chess.square_rank(move.from_square) != home:
                    continue  # only count leaving the back rank as development
                if not self._safe(board, move):
                    continue
                gain = self._move_pst_gain(board, move)
                if gain > best_gain:
                    best_gain, best = gain, move
            if best is not None:
                return best, label
        return None

    # --- rule 7 -----------------------------------------------------------
    def _rule_center_pawn(self, board) -> Optional[Candidate]:
        for move in board.legal_moves:
            mover = board.piece_at(move.from_square)
            if mover is None or mover.piece_type != chess.PAWN:
                continue
            if move.to_square in CENTER and self._safe(board, move):
                return move, "stake a center pawn"
        return None

    # --- rule 8 -----------------------------------------------------------
    def _rule_rook_open_file(self, board) -> Optional[Candidate]:
        us = board.turn
        best = None
        best_score = 0
        for move in board.legal_moves:
            mover = board.piece_at(move.from_square)
            if mover is None or mover.piece_type != chess.ROOK:
                continue
            if not self._safe(board, move):
                continue
            score = open_file_score(board, chess.square_file(move.to_square), us)
            if score > best_score:
                best_score, best = score, move
        if best is not None:
            return best, "put a rook on an open file"
        return None

    # --- rule 9 -----------------------------------------------------------
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
            best = None
            best_to = current
            for move in board.legal_moves:
                if move.from_square != sq or not self._safe(board, move):
                    continue
                board.push(move)
                placed = _piece_pst(board, move.to_square)
                board.pop()
                if placed > best_to:
                    best_to, best = placed, move
            if best is not None:
                return best, "improve the worst-placed piece"
        return None

    # --- rule 10 ----------------------------------------------------------
    def _rule_waiting(self, board) -> Optional[Candidate]:
        legal = list(board.legal_moves)
        if not legal:
            return None
        safe = [m for m in legal if self._safe(board, m)]
        pool = safe or legal
        # Prefer a move that nudges placement upward.
        best = max(pool, key=lambda m: self._move_pst_gain(board, m))
        return best, "safe waiting move"

    # --- safety filter ----------------------------------------------------
    def _safe(self, board: chess.Board, move: chess.Move) -> bool:
        """1-ply veto: do not hang material to a recapture, do not allow mate-in-1."""
        return not self._allows_mate(board, move) and not self._hangs_material(board, move)

    @staticmethod
    def _allows_mate(board: chess.Board, move: chess.Move) -> bool:
        board.push(move)
        try:
            return mate_in_1(board) is not None
        finally:
            board.pop()

    @staticmethod
    def _hangs_material(board: chess.Board, move: chess.Move) -> bool:
        if board.is_capture(move):
            # A capture is fine as long as the exchange does not lose material.
            return see_gain(board, move) < 0
        board.push(move)
        try:
            return is_hanging(board, move.to_square)
        finally:
            board.pop()

    @staticmethod
    def _move_pst_gain(board: chess.Board, move: chess.Move) -> float:
        before = _piece_pst(board, move.from_square)
        board.push(move)
        try:
            after = _piece_pst(board, move.to_square)
        finally:
            board.pop()
        return after - before


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
