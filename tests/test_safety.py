"""The critical safety battery — runs against every engine.

Over a range of positions (including near-stalemate and forced lines) every engine
must return a *legal* move, inside its time budget, and never raise.  We also force
an internal exception and confirm the random-legal fallback fires.
"""

import time

import chess
import pytest

from retro import harness
from retro.engines import ENGINES, engine_names, get_engine
from retro.timeman import TimeLimits

# A spread of positions: opening, midgame, endgames, checks, and forced/near-stale.
BATTERY = [
    chess.STARTING_FEN,
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "r3k2r/pppq1ppp/2np1n2/2b1p1B1/2B1P1b1/2NP1N2/PPPQ1PPP/R3K2R w KQkq - 0 1",
    "8/8/8/8/8/5k2/6q1/7K w - - 0 1",        # white to move, almost stalemated
    "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1",         # black to move, only sad replies
    "8/8/8/4k3/8/8/4K3/8 w - - 0 1",          # bare kings
    "6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1",      # mate in one available
    "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3",  # in check
    "8/P6k/8/8/8/8/7K/8 w - - 0 1",           # promotion available
    "k7/8/1K6/8/8/8/8/1Q6 w - - 0 1",         # easy mate-ish, tiny mobility
]


def _move_quickly(engine, board):
    limits = TimeLimits(movetime=0.25)
    start = time.monotonic()
    move = harness.safe_choose(engine, board, limits)
    elapsed = time.monotonic() - start
    return move, elapsed


@pytest.mark.parametrize("name", engine_names())
@pytest.mark.parametrize("fen", BATTERY)
def test_engine_always_legal_and_in_time(name, fen):
    board = chess.Board(fen)
    engine = get_engine(name)
    legal = list(board.legal_moves)

    move, elapsed = _move_quickly(engine, board)

    if not legal:
        assert move is None  # game already over
    else:
        assert move in legal, f"{name} returned illegal move {move} on {fen}"
    # Generous ceiling: 0.25s budget + harness grace, with slack for slow CI.
    assert elapsed < 2.0, f"{name} took {elapsed:.2f}s on {fen}"


class _Exploding:
    """An engine whose search always raises — exercises the fallback path."""

    name = "BOOM"
    author = "test"

    def choose_move(self, board, limits):
        raise RuntimeError("kaboom")


def test_fallback_fires_on_exception():
    board = chess.Board()
    move = harness.safe_choose(_Exploding(), board, TimeLimits(movetime=0.1))
    assert move in set(board.legal_moves)


class _Illegal:
    """An engine that returns an illegal move — the harness must reject it."""

    name = "CHEAT"
    author = "test"

    def choose_move(self, board, limits):
        return chess.Move.from_uci("e2e5")  # not legal from the start position


def test_illegal_move_is_replaced_with_legal():
    board = chess.Board()
    move = harness.safe_choose(_Illegal(), board, TimeLimits(movetime=0.1))
    assert move in set(board.legal_moves)


class _Slow:
    """An engine that ignores the cooperative deadline — hard deadline must catch it."""

    name = "SLOW"
    author = "test"

    def choose_move(self, board, limits):
        time.sleep(5.0)
        return chess.Move.from_uci("e2e4")


def test_hard_deadline_catches_runaway():
    board = chess.Board()
    start = time.monotonic()
    move = harness.safe_choose(_Slow(), board, TimeLimits(movetime=0.1))
    elapsed = time.monotonic() - start
    assert move in set(board.legal_moves)
    assert elapsed < 2.0  # we did not wait the full 5 seconds


def test_no_legal_moves_returns_none():
    # Fool's mate: white is checkmated and has no legal moves.
    mated = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert mated.is_checkmate()
    assert harness.safe_choose(get_engine("kneejerk"), mated, TimeLimits(movetime=0.1)) is None


def test_registry_has_all_engines():
    assert set(ENGINES) == {"turampion", "shannstein", "copybook", "kneejerk",
                            "beeline", "mirror"}
