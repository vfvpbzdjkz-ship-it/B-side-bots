"""Tactics helpers: mate_in_1, is_hanging, see_gain on hand-built FENs."""

import chess

from retro.common import tactics
from retro.common.evalutil import PIECE_VALUES


def test_mate_in_1_back_rank():
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1")
    move = tactics.mate_in_1(board)
    assert move == chess.Move.from_uci("a1a8")


def test_mate_in_1_none_when_no_mate():
    assert tactics.mate_in_1(chess.Board()) is None


def test_is_hanging_undefended_piece():
    # Black knight on d4 attacked by a white pawn, undefended -> hanging.
    board = chess.Board("4k3/8/8/8/3n4/2P5/8/4K3 w - - 0 1")
    assert tactics.is_hanging(board, chess.D4) is True


def test_is_hanging_defended_equal_piece():
    # Knight on d4 attacked by a pawn and defended by a bishop on a7; the pawn is
    # cheaper than the knight, so it is still hanging (a pawn wins a knight).
    board = chess.Board("4k3/b7/8/8/3n4/2P5/8/4K3 w - - 0 1")
    assert tactics.is_hanging(board, chess.D4) is True


def test_is_not_hanging_when_safely_defended():
    # Rook attacks the knight, knight defended by a black pawn on c5; the attacker
    # (rook) is dearer than the knight and not outnumbered -> not hanging.
    board = chess.Board("4k3/8/8/2p5/3n4/8/8/3RK3 w - - 0 1")
    assert tactics.is_hanging(board, chess.D4) is False


def test_is_hanging_empty_square():
    assert tactics.is_hanging(chess.Board(), chess.E4) is False


def test_see_gain_free_capture():
    # White rook takes an undefended black bishop -> gain a full bishop.
    board = chess.Board("4k3/8/8/8/8/8/3b4/3RK3 w - - 0 1")
    move = chess.Move.from_uci("d1d2")
    assert tactics.see_gain(board, move) == PIECE_VALUES[chess.BISHOP]


def test_see_gain_defended_capture():
    # Rook takes a bishop that is defended by a pawn: bishop - rook (we get hit back).
    board = chess.Board("4k3/8/8/8/8/2p5/3b4/3RK3 w - - 0 1")
    move = chess.Move.from_uci("d1d2")
    expected = PIECE_VALUES[chess.BISHOP] - PIECE_VALUES[chess.ROOK]
    assert tactics.see_gain(board, move) == expected


def test_see_gain_non_capture_is_zero():
    assert tactics.see_gain(chess.Board(), chess.Move.from_uci("e2e4")) == 0
