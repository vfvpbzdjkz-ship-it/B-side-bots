"""Per-engine behavior checks (the fun, characterful ones)."""

import chess

from retro.timeman import TimeLimits
from retro.engines import get_engine
from retro.engines.shannstein import Shannstein, K
from retro.common.evalutil import PIECE_VALUES
from retro.common.tactics import see_gain


def _choose(name, fen, movetime=0.4):
    board = chess.Board(fen)
    engine = get_engine(name)
    move = engine.choose_move(board, TimeLimits(movetime=movetime))
    return board, engine, move


# --- TURAMPION ------------------------------------------------------------

def test_turampion_wins_a_free_exchange():
    # A free queen down an open file: the dead search must see there is no
    # recapture and grab it rather than shuffling.
    board, _, move = _choose("turampion", "4k3/8/8/3q4/8/8/3Q4/4K3 w - - 0 1")
    assert board.is_capture(move)
    assert see_gain(board, move) >= PIECE_VALUES[chess.QUEEN] - 1
    assert move == chess.Move.from_uci("d2d5")


def test_turampion_doesnt_blunder_back_the_exchange():
    # Winning a defended rook with a queen would lose material; it should decline.
    board, _, move = _choose("turampion", "4k3/3r4/8/8/8/8/3Q4/4K3 w - - 0 1")
    # Whatever it plays, it must not give away the queen for the rook.
    assert see_gain(board, move) >= 0


# --- SHANNSTEIN -----------------------------------------------------------

def test_shannstein_keeps_all_moves_when_fewer_than_k():
    # A cramped king-and-pawn position with very few legal moves: the forward
    # pruner must keep *all* of them (the mandatory fallback).
    board = chess.Board("7k/8/8/8/8/8/8/K7 w - - 0 1")
    legal = list(board.legal_moves)
    assert len(legal) < K
    kept = Shannstein._plausible_moves(board)
    assert set(kept) == set(legal)


def test_shannstein_prunes_to_k_when_many_moves():
    board = chess.Board()  # 20 legal moves at the start
    kept = Shannstein._plausible_moves(board)
    assert len(kept) == K


def test_shannstein_always_has_a_move_in_forced_line():
    # In check with a single legal reply — must return it.
    board = chess.Board("4k3/8/8/8/8/8/5q2/4K3 w - - 0 1")
    _, _, move = _choose("shannstein", board.fen())
    assert move in set(board.legal_moves)


# --- COPYBOOK -------------------------------------------------------------

def test_copybook_plays_mate_and_narrates_rule_1():
    board, engine, move = _choose("copybook", "6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1")
    assert board.is_checkmate() is False
    assert move == chess.Move.from_uci("a1a8")
    assert engine.narration == "rule 1: deliver mate"


def test_copybook_plays_opening_book_from_startpos():
    # "By the book": the start position is theory, so COPYBOOK plays a known first
    # move and names the opening.
    board, engine, move = _choose("copybook", chess.STARTING_FEN)
    assert move in set(board.legal_moves)
    assert engine.narration.startswith("book:")
    assert move.uci() in {"e2e4", "d2d4", "c2c4", "g1f3"}


def test_copybook_follows_book_into_a_named_opening():
    # After 1.e4 e5 2.Nf3 Nc6 the position is still theory; COPYBOOK keeps booking.
    board = chess.Board()
    for uci in ("e2e4", "e7e5", "g1f3", "b8c6"):
        board.push_uci(uci)
    engine = get_engine("copybook")
    move = engine.choose_move(board, TimeLimits(movetime=0.2))
    assert move in set(board.legal_moves)
    assert engine.narration.startswith("book:")  # e.g. Ruy Lopez / Italian / Scotch


def test_copybook_develops_a_knight_out_of_book():
    # A non-theoretical position where nothing else fires: the maxim cascade should
    # develop a knight off the back rank.
    board, engine, move = _choose("copybook", "4k3/8/8/8/8/8/8/1N2K3 w - - 0 1")
    mover = board.piece_at(move.from_square)
    assert mover.piece_type == chess.KNIGHT
    assert engine.narration == "rule 6: develop a knight"


def test_copybook_pushes_a_passed_pawn_in_the_endgame():
    # King-and-pawn endgame with a clear passed pawn and nothing tactical: the
    # endgame maxim should advance it.
    board, engine, move = _choose("copybook", "8/8/8/4k3/8/2P5/8/4K3 w - - 0 1")
    assert move.uci() in {"c3c4"}
    assert engine.narration == "rule 9: push a passed pawn"


def test_copybook_takes_a_free_capture_rule_3():
    # Nothing forcing; a free pawn is hanging -> rule 3 (best safe capture).
    board, engine, move = _choose("copybook", "4k3/8/8/8/3p4/4P3/8/4K3 w - - 0 1")
    assert board.is_capture(move)
    assert engine.narration.startswith("rule 3")


# --- KNEEJERK -------------------------------------------------------------

def test_kneejerk_develops_on_move_one():
    board, _, move = _choose("kneejerk", chess.STARTING_FEN, movetime=0.1)
    mover = board.piece_at(move.from_square)
    # Coherent development with zero lookahead: a knight comes off the back rank.
    assert mover.piece_type == chess.KNIGHT
    assert chess.square_rank(move.from_square) == 0


# --- MIRROR ---------------------------------------------------------------

def test_mirror_copies_the_opponents_move():
    board = chess.Board()
    board.push_uci("e2e4")  # White moves; MIRROR (Black) should reply e7e5.
    engine = get_engine("mirror")
    move = engine.choose_move(board, TimeLimits(movetime=0.2))
    assert move == chess.Move.from_uci("e7e5")


def test_mirror_handles_castling_reflection():
    # White castles kingside; the mirror image is Black castling kingside.
    board = chess.Board("rnbqk2r/pppp1ppp/5n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    board.push_uci("e1g1")
    engine = get_engine("mirror")
    move = engine.choose_move(board, TimeLimits(movetime=0.2))
    assert move == chess.Move.from_uci("e8g8")


def test_mirror_falls_back_to_a_legal_move_when_reflection_illegal():
    # 1.e4 c5 2.Bb5 — Black's c5 pawn blocks the mirror image (...Bb4), so the
    # reflection is illegal and MIRROR must delegate to a sibling engine.
    board = chess.Board()
    for uci in ("e2e4", "c7c5", "f1b5"):
        board.push_uci(uci)
    assert chess.Move.from_uci("f8b4") not in board.legal_moves  # mirror is illegal
    move = get_engine("mirror").choose_move(board, TimeLimits(movetime=0.3))
    assert move in set(board.legal_moves)


def test_mirror_with_no_history_still_legal():
    board = chess.Board()  # no moves yet -> nothing to mirror
    move = get_engine("mirror").choose_move(board, TimeLimits(movetime=0.3))
    assert move in set(board.legal_moves)


# --- BEELINE --------------------------------------------------------------

def test_beeline_steers_a_piece_toward_the_enemy_king():
    fen = "7k/8/8/8/8/8/8/3Q3K w - - 0 1"
    board, _, move = _choose("beeline", fen, movetime=0.4)
    enemy_king = board.king(chess.BLACK)
    before = chess.square_distance(move.from_square, enemy_king)
    after = chess.square_distance(move.to_square, enemy_king)
    # It marches a piece closer to the enemy king (and does not hang it as a rule).
    assert after < before
    assert board.piece_at(move.from_square).piece_type == chess.QUEEN
