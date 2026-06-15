"""Perft sanity — confirms python-chess move generation matches known counts."""

import chess
import pytest


def perft(board: chess.Board, depth: int) -> int:
    if depth == 0:
        return 1
    nodes = 0
    for move in board.legal_moves:
        board.push(move)
        nodes += perft(board, depth - 1)
        board.pop()
    return nodes


# Canonical perft node counts from the start position.
START_PERFT = {1: 20, 2: 400, 3: 8902, 4: 197281}


@pytest.mark.parametrize("depth,expected", sorted(START_PERFT.items()))
def test_startpos_perft(depth, expected):
    assert perft(chess.Board(), depth) == expected
