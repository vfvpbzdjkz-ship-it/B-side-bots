"""The positional refinement layer: pawn kicks, outposts, the rim, tempo."""

import chess

from retro.common.positional import assess


def _reasons(fen, uci):
    board = chess.Board(fen)
    delta, reasons = assess(board, chess.Move.from_uci(uci))
    return delta, reasons


def test_safe_development_is_rewarded_and_explained():
    # Knight b1->c3 with no enemy pawn able to hit c3: safe from kicks.
    delta, reasons = _reasons("4k3/8/8/8/8/8/8/1N2K3 w - - 0 1", "b1c3")
    assert "safe from pawn kicks" in reasons
    assert delta > 0


def test_kickable_square_is_penalized():
    # Same knight to c3, but a black pawn on b5 can play ...b4 to kick it.
    delta, reasons = _reasons("4k3/8/8/1p6/8/8/8/1N2K3 w - - 0 1", "b1c3")
    assert "safe from pawn kicks" not in reasons
    assert delta < 0


def test_outpost_is_recognized():
    # Knight c3->d5, defended by the e4 pawn and unkickable: an outpost.
    delta, reasons = _reasons("4k3/8/8/8/4P3/2N5/8/4K3 w - - 0 1", "c3d5")
    assert "to an outpost" in reasons
    assert delta >= 25


def test_knight_on_the_rim_scores_worse_than_the_center():
    center, _ = _reasons("4k3/8/8/8/8/8/8/1N2K3 w - - 0 1", "b1c3")
    rim, _ = _reasons("4k3/8/8/8/8/8/8/1N2K3 w - - 0 1", "b1a3")
    assert rim < center  # "a knight on the rim is dim"


def test_developing_with_tempo_is_flagged():
    # Bishop to b5+ hits the king / pins; here Bf1-b5 attacks the knight on c6.
    board = chess.Board("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/8/PPPP1PPP/RNBQK1NR b KQkq - 0 1")
    # Construct from White's side: a bishop move that attacks a piece -> "with tempo".
    delta, reasons = _reasons(
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1", "f1b5")
    assert "with tempo" in reasons
