"""Minimal UCI driver shared by every engine.

Reads UCI commands on stdin, drives the selected engine through the harness, and
writes ``bestmove`` (plus ``info string`` narration for COPYBOOK) on stdout.  The
engine is chosen by the ``ENGINE`` environment variable or ``--engine`` flag.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

import chess

from . import harness
from .engines import DEFAULT_ENGINE, get_engine
from .timeman import TimeLimits


class UCIDriver:
    def __init__(self, engine, out=None) -> None:
        self.engine = engine
        self.board = chess.Board()
        self.out = out if out is not None else sys.stdout

    # --- output ----------------------------------------------------------
    def _send(self, text: str) -> None:
        self.out.write(text + "\n")
        self.out.flush()

    # --- main loop -------------------------------------------------------
    def run(self, lines=None) -> None:
        stream = lines if lines is not None else sys.stdin
        for raw in stream:
            line = raw.strip()
            if not line:
                continue
            if not self.handle(line):
                break

    def handle(self, line: str) -> bool:
        """Process one command. Return False to quit the loop."""
        parts = line.split()
        command = parts[0]

        if command == "uci":
            self._send(f"id name {self.engine.name}")
            self._send(f"id author {self.engine.author}")
            self._send("uciok")
        elif command == "isready":
            self._send("readyok")
        elif command == "ucinewgame":
            self.board.reset()
            if hasattr(self.engine, "new_game"):
                self.engine.new_game()
        elif command == "position":
            self._set_position(parts[1:])
        elif command == "go":
            self._go(parts[1:])
        elif command == "stop":
            pass  # search is synchronous; nothing to interrupt
        elif command in ("quit", "exit"):
            return False
        # Unknown commands are ignored per the UCI spec.
        return True

    # --- position --------------------------------------------------------
    def _set_position(self, args: List[str]) -> None:
        if not args:
            return
        if args[0] == "startpos":
            self.board.reset()
            rest = args[1:]
        elif args[0] == "fen":
            fen = " ".join(args[1:7])
            self.board.set_fen(fen)
            rest = args[7:]
        else:
            return

        if rest and rest[0] == "moves":
            for token in rest[1:]:
                self.board.push_uci(token)

    # --- go --------------------------------------------------------------
    def _go(self, args: List[str]) -> None:
        limits = _parse_go(args)
        move = harness.safe_choose(self.engine, self.board, limits)

        narration = getattr(self.engine, "narration", "")
        if narration:
            self._send(f"info string {narration}")

        if move is None:
            self._send("bestmove 0000")  # game over / no legal moves
        else:
            self._send(f"bestmove {move.uci()}")


def _parse_go(args: List[str]) -> TimeLimits:
    """Turn ``go`` arguments (milliseconds) into a TimeLimits (seconds)."""
    limits = TimeLimits()
    i = 0
    while i < len(args):
        token = args[i]
        if token == "movetime":
            limits.movetime = _ms(args, i + 1)
            i += 2
        elif token == "wtime":
            limits.wtime = _ms(args, i + 1)
            i += 2
        elif token == "btime":
            limits.btime = _ms(args, i + 1)
            i += 2
        elif token == "winc":
            limits.winc = _ms(args, i + 1) or 0.0
            i += 2
        elif token == "binc":
            limits.binc = _ms(args, i + 1) or 0.0
            i += 2
        elif token == "depth":
            limits.depth = _int(args, i + 1)
            i += 2
        else:
            # infinite, ponder, nodes, searchmoves, ... — ignored in v1.
            i += 1
    return limits


def _ms(args: List[str], index: int) -> Optional[float]:
    value = _int(args, index)
    return None if value is None else value / 1000.0


def _int(args: List[str], index: int) -> Optional[int]:
    if 0 <= index < len(args):
        try:
            return int(args[index])
        except ValueError:
            return None
    return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="RETRO ROSTER UCI driver")
    parser.add_argument(
        "--engine",
        default=os.environ.get("ENGINE", DEFAULT_ENGINE),
        help="which engine strategy to load (or set ENGINE=...)",
    )
    opts = parser.parse_args(argv)

    engine = get_engine(opts.engine)
    UCIDriver(engine).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
