"""A small built-in opening book of named mainlines — "playing by the book".

This is deliberately *not* a search: it is literal chess-book knowledge.  COPYBOOK
consults it first and, while the position is still theory, plays the booked move and
names the opening (``info string book: Ruy Lopez``).  Once the game leaves known
territory the book returns ``None`` and the principle-based maxims take over.

The book is keyed by position (piece placement + side to move + castling + en
passant), so it follows theory through transpositions and works for either colour.
"""

from __future__ import annotations

import random
from typing import Dict, Optional, Tuple

import chess

# name -> mainline in SAN.  Curated popular theory, a handful of moves deep.
LINES = {
    "Ruy Lopez": "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O",
    "Italian Game": "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3 d6 O-O O-O",
    "Scotch Game": "e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nf6 Nc3 Bb4",
    "Petrov Defense": "e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4 d4 d5 Bd3 Be7",
    "Four Knights": "e4 e5 Nf3 Nc6 Nc3 Nf6 Bb5 Bb4 O-O O-O",
    "Sicilian Najdorf": "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be2 e5 Nb3 Be7",
    "Sicilian Classical": "e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 Nf6 Nc3 d6 Be2 e5",
    "French Defense": "e4 e6 d4 d5 Nc3 Nf6 e5 Nfd7 f4 c5",
    "Caro-Kann": "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 h4 h6",
    "Scandinavian": "e4 d5 exd5 Qxd5 Nc3 Qa5 d4 Nf6 Nf3 c6",
    "Pirc Defense": "e4 d6 d4 Nf6 Nc3 g6 Nf3 Bg7 Be2 O-O",
    "Queen's Gambit Declined": "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3 h6",
    "Queen's Gambit Accepted": "d4 d5 c4 dxc4 Nf3 Nf6 e3 e6 Bxc4 c5 O-O a6",
    "Slav Defense": "d4 d5 c4 c6 Nf3 Nf6 Nc3 dxc4 a4 Bf5 e3 e6",
    "King's Indian Defense": "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5",
    "Nimzo-Indian": "d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5",
    "Queen's Indian": "d4 Nf6 c4 e6 Nf3 b6 g3 Bb7 Bg2 Be7",
    "Grunfeld Defense": "d4 Nf6 c4 g6 Nc3 d5 cxd5 Nxd5 e4 Nxc3 bxc3 Bg7",
    "Catalan": "d4 Nf6 c4 e6 g3 d5 Bg2 Be7 Nf3 O-O O-O dxc4",
    "English Opening": "c4 e5 Nc3 Nf6 Nf3 Nc6 g3 d5 cxd5 Nxd5",
    "London System": "d4 d5 Bf4 Nf6 e3 e6 Nf3 Bd6 Bg3 O-O",
    "Reti Opening": "Nf3 d5 c4 e6 g3 Nf6 Bg2 Be7 O-O O-O",
}


def _key(board: chess.Board) -> str:
    """Position key: placement + turn + castling + en passant (clock-agnostic)."""
    return " ".join(board.fen().split()[:4])


def _build_book() -> Dict[str, Dict[str, str]]:
    """position key -> {uci move: opening name}."""
    book: Dict[str, Dict[str, str]] = {}
    for name, line in LINES.items():
        board = chess.Board()
        for san in line.split():
            try:
                move = board.parse_san(san)
            except ValueError:
                break  # bad line; stop recording it
            book.setdefault(_key(board), {}).setdefault(move.uci(), name)
            board.push(move)
    return book


BOOK = _build_book()


def book_move(board: chess.Board) -> Optional[Tuple[chess.Move, str]]:
    """Return a booked ``(move, opening name)`` for this position, or ``None``.

    When several theory moves are available (e.g. choosing a defence to 1.e4) one
    is picked at random for variety, so COPYBOOK doesn't play the same line forever.
    """
    entry = BOOK.get(_key(board))
    if not entry:
        return None
    uci, name = random.choice(list(entry.items()))
    move = chess.Move.from_uci(uci)
    if move in board.legal_moves:
        return move, name
    return None
