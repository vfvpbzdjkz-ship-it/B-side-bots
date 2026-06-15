"""Tapered eval: mirror symmetry and phase interpolation."""

import chess

from retro.common import evalutil


MIRROR_FENS = [
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    "r2q1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 1",
    "8/5k2/8/8/3Q4/8/2K5/8 w - - 0 1",
]


def test_evaluate_is_color_symmetric():
    # Mirroring a position vertically and swapping colors must negate the score.
    for fen in MIRROR_FENS:
        board = chess.Board(fen)
        score = evalutil.evaluate(board)
        mirrored = evalutil.evaluate(board.mirror())
        assert mirrored == -score, f"asymmetric eval for {fen}"


def test_startpos_is_balanced():
    assert evalutil.evaluate(chess.Board()) == 0


def test_phase_is_middlegame_at_full_material():
    # Full starting material -> phase saturated at the max, mg weight == 1.0.
    board = chess.Board()
    assert evalutil.game_phase(board) == evalutil.PHASE_MAX
    mg_w, eg_w = evalutil.phase_weights(board)
    assert mg_w == 1.0
    assert eg_w == 0.0


def test_phase_is_endgame_in_bare_king_ending():
    # Two bare kings -> phase 0, fully endgame.
    board = chess.Board("8/4k3/8/8/8/8/4K3/8 w - - 0 1")
    assert evalutil.game_phase(board) == 0
    mg_w, eg_w = evalutil.phase_weights(board)
    assert mg_w == 0.0
    assert eg_w == 1.0


def test_phase_interpolates_between():
    # A single queen each side sits strictly between the extremes.
    board = chess.Board("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1")
    phase = evalutil.game_phase(board)
    assert 0 < phase < evalutil.PHASE_MAX


def test_material_counts_extra_piece():
    # White up a full knight.
    board = chess.Board("rnbqkb1r/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert evalutil.material(board) == evalutil.PIECE_VALUES[chess.KNIGHT]
