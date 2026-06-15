"""A small Tkinter GUI for the RETRO ROSTER — pick an engine and play it.

Pure standard library (Tkinter ships with CPython), so it runs anywhere Python
runs, including a double-clickable ``.pyw`` on Windows.  Click a piece, click a
destination; the chosen engine replies on a background thread so the window never
freezes.  COPYBOOK's rule narration is shown in the status bar.

Launch with ``python -m retro.gui`` (or double-click ``RetroRoster.pyw`` on Windows).
"""

from __future__ import annotations

import sys
import threading

import chess

from . import harness
from .engines import DEFAULT_ENGINE, engine_names, get_engine
from .timeman import TimeLimits

# Unicode glyphs for the pieces.
_GLYPHS = {
    (chess.PAWN, chess.WHITE): "♙", (chess.PAWN, chess.BLACK): "♟",
    (chess.KNIGHT, chess.WHITE): "♘", (chess.KNIGHT, chess.BLACK): "♞",
    (chess.BISHOP, chess.WHITE): "♗", (chess.BISHOP, chess.BLACK): "♝",
    (chess.ROOK, chess.WHITE): "♖", (chess.ROOK, chess.BLACK): "♜",
    (chess.QUEEN, chess.WHITE): "♕", (chess.QUEEN, chess.BLACK): "♛",
    (chess.KING, chess.WHITE): "♔", (chess.KING, chess.BLACK): "♚",
}

LIGHT = "#f0d9b5"
DARK = "#b58863"
HILITE = "#6ca0dc"
LASTMOVE = "#cdd26a"
SQUARE = 64
MOVETIME = 1.0  # seconds the engine is allowed per move


class RetroRosterGUI:
    def __init__(self, root) -> None:
        import tkinter as tk

        self.tk = tk
        self.root = root
        root.title("RETRO ROSTER")

        self.board = chess.Board()
        self.engine_name = tk.StringVar(value=DEFAULT_ENGINE)
        self.human_color = chess.WHITE
        self.engine = get_engine(self.engine_name.get())
        self.selected = None          # square the human picked first
        self.last_move = None
        self.thinking = False

        self._build_controls()
        self._build_board()
        self._build_status()
        self.redraw()

    # --- layout ----------------------------------------------------------
    def _build_controls(self) -> None:
        tk = self.tk
        bar = tk.Frame(self.root, padx=8, pady=6)
        bar.pack(fill="x")

        tk.Label(bar, text="Engine:").pack(side="left")
        menu = tk.OptionMenu(bar, self.engine_name, *engine_names(),
                             command=lambda _=None: self._switch_engine())
        menu.pack(side="left", padx=(2, 12))

        tk.Button(bar, text="New game (play White)",
                  command=lambda: self.new_game(chess.WHITE)).pack(side="left")
        tk.Button(bar, text="Play Black",
                  command=lambda: self.new_game(chess.BLACK)).pack(side="left", padx=4)
        tk.Button(bar, text="Take back", command=self.take_back).pack(side="left", padx=4)

    def _build_board(self) -> None:
        tk = self.tk
        self.canvas = tk.Canvas(self.root, width=8 * SQUARE, height=8 * SQUARE,
                                highlightthickness=0)
        self.canvas.pack(padx=8)
        self.canvas.bind("<Button-1>", self._on_click)

    def _build_status(self) -> None:
        tk = self.tk
        self.status = tk.StringVar(value="Your move.")
        bar = tk.Frame(self.root, padx=8, pady=6)
        bar.pack(fill="x")
        tk.Label(bar, textvariable=self.status, anchor="w").pack(fill="x")

    # --- drawing ---------------------------------------------------------
    def _square_to_xy(self, square: int):
        """Top-left pixel of ``square``, honoring board orientation."""
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self.human_color == chess.WHITE:
            col, row = file, 7 - rank
        else:
            col, row = 7 - file, rank
        return col * SQUARE, row * SQUARE

    def _xy_to_square(self, x: int, y: int):
        col, row = x // SQUARE, y // SQUARE
        if not (0 <= col < 8 and 0 <= row < 8):
            return None
        if self.human_color == chess.WHITE:
            file, rank = col, 7 - row
        else:
            file, rank = 7 - col, row
        return chess.square(file, rank)

    def redraw(self) -> None:
        self.canvas.delete("all")
        for square in chess.SQUARES:
            x, y = self._square_to_xy(square)
            light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            color = LIGHT if light else DARK
            if self.last_move and square in (self.last_move.from_square,
                                             self.last_move.to_square):
                color = LASTMOVE
            if square == self.selected:
                color = HILITE
            self.canvas.create_rectangle(x, y, x + SQUARE, y + SQUARE,
                                         fill=color, outline=color)
            piece = self.board.piece_at(square)
            if piece is not None:
                self.canvas.create_text(
                    x + SQUARE // 2, y + SQUARE // 2,
                    text=_GLYPHS[(piece.piece_type, piece.color)],
                    font=("DejaVu Sans", SQUARE - 18),
                )
        self.root.update_idletasks()

    # --- interaction -----------------------------------------------------
    def _on_click(self, event) -> None:
        if self.thinking or self.board.is_game_over():
            return
        if self.board.turn != self.human_color:
            return
        square = self._xy_to_square(event.x, event.y)
        if square is None:
            return

        if self.selected is None:
            piece = self.board.piece_at(square)
            if piece is not None and piece.color == self.human_color:
                self.selected = square
                self.redraw()
            return

        move = self._build_move(self.selected, square)
        self.selected = None
        if move is not None and move in self.board.legal_moves:
            self._play(move)
        else:
            self.redraw()  # illegal: just clear the selection

    def _build_move(self, frm: int, to: int):
        """Construct the move, auto-queening pawn promotions for simplicity."""
        piece = self.board.piece_at(frm)
        promotion = None
        if piece is not None and piece.piece_type == chess.PAWN \
                and chess.square_rank(to) in (0, 7):
            promotion = chess.QUEEN
        return chess.Move(frm, to, promotion=promotion)

    def _play(self, move: chess.Move) -> None:
        self.board.push(move)
        self.last_move = move
        self.redraw()
        if self._announce_if_over():
            return
        self._engine_move()

    # --- engine ----------------------------------------------------------
    def _engine_move(self) -> None:
        self.thinking = True
        self.status.set(f"{self.engine.name} is thinking…")
        self.root.update_idletasks()

        def work():
            limits = TimeLimits(movetime=MOVETIME)
            move = harness.safe_choose(self.engine, self.board.copy(), limits)
            narration = getattr(self.engine, "narration", "")
            self.root.after(0, lambda: self._engine_done(move, narration))

        threading.Thread(target=work, daemon=True).start()

    def _engine_done(self, move, narration) -> None:
        self.thinking = False
        if move is None or move not in self.board.legal_moves:
            self._announce_if_over()
            return
        self.board.push(move)
        self.last_move = move
        self.redraw()
        note = f"  ({narration})" if narration else ""
        if not self._announce_if_over():
            self.status.set(f"{self.engine.name} played {move.uci()}.{note}  Your move.")

    # --- game state ------------------------------------------------------
    def _announce_if_over(self) -> bool:
        if not self.board.is_game_over():
            return False
        if self.board.is_checkmate():
            winner = "White" if self.board.turn == chess.BLACK else "Black"
            self.status.set(f"Checkmate — {winner} wins.")
        elif self.board.is_stalemate():
            self.status.set("Stalemate — draw.")
        else:
            self.status.set("Game over — draw.")
        return True

    def new_game(self, human_color: chess.Color) -> None:
        self.board.reset()
        if hasattr(self.engine, "new_game"):
            self.engine.new_game()
        self.human_color = human_color
        self.selected = None
        self.last_move = None
        self.thinking = False
        self.status.set("Your move." if human_color == chess.WHITE
                        else f"{self.engine.name} to move…")
        self.redraw()
        if human_color == chess.BLACK:
            self._engine_move()

    def take_back(self) -> None:
        if self.thinking:
            return
        # Undo a full move (engine reply + your move) so it is your turn again.
        for _ in range(2):
            if self.board.move_stack:
                self.board.pop()
        self.last_move = self.board.peek() if self.board.move_stack else None
        self.selected = None
        self.status.set("Your move.")
        self.redraw()

    def _switch_engine(self) -> None:
        self.engine = get_engine(self.engine_name.get())
        self.status.set(f"Switched to {self.engine.name}. Start a new game to use it.")


def main() -> int:
    try:
        import tkinter as tk
    except Exception:  # noqa: BLE001
        sys.stderr.write(
            "Tkinter is not available in this Python build.\n"
            "Install it (e.g. `sudo apt install python3-tk`) or use the UCI driver "
            "directly via run.sh.\n"
        )
        return 1
    root = tk.Tk()
    RetroRosterGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
