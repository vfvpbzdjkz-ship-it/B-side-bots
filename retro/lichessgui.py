"""The "Play on Lichess" window for the GUI.

Lets you paste a Lichess **bot** API token (saved across runs), pick which engine
plays, browse a scrollable list of online bots, choose casual/rated, colour and
time control, then challenge a bot and watch the game play out on the main board —
your chosen engine making every move through the Bot API.

Everything network-facing runs on a background thread; all widget updates are
marshalled back onto the Tk main loop via ``root.after``.
"""

from __future__ import annotations

import threading
from typing import Optional

import chess

from . import harness
from .engines import engine_names, get_engine
from .lichess import LichessClient, LichessError, load_settings, save_settings
from .timeman import TimeLimits

# Convenient time-control presets: (label, minutes, increment-seconds).
TIME_PRESETS = [
    ("1+0 Bullet", 1.0, 0),
    ("2+1 Bullet", 2.0, 1),
    ("3+0 Blitz", 3.0, 0),
    ("3+2 Blitz", 3.0, 2),
    ("5+3 Blitz", 5.0, 3),
    ("10+0 Rapid", 10.0, 0),
    ("15+10 Rapid", 15.0, 10),
]


class LichessWindow:
    def __init__(self, app) -> None:
        import tkinter as tk

        self.tk = tk
        self.app = app
        self.root = app.root
        self.settings = load_settings()
        self.stop_flag = threading.Event()
        self.playing = False
        self.game_id: Optional[str] = None
        self.client: Optional[LichessClient] = None

        self.win = tk.Toplevel(self.root)
        self.win.title("Play on Lichess")
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        self._apply_settings()

    # --- layout ----------------------------------------------------------
    def _build(self) -> None:
        tk = self.tk
        pad = {"padx": 6, "pady": 3}

        # Token row
        tok = tk.LabelFrame(self.win, text="Lichess bot API token", padx=6, pady=6)
        tok.pack(fill="x", **pad)
        self.token_var = tk.StringVar()
        self.token_entry = tk.Entry(tok, textvariable=self.token_var, show="•", width=42)
        self.token_entry.pack(side="left", fill="x", expand=True)
        tk.Button(tok, text="Save", command=self._save).pack(side="left", padx=4)
        tk.Button(tok, text="Verify", command=self._verify).pack(side="left")

        # Options row
        opts = tk.Frame(self.win)
        opts.pack(fill="x", **pad)

        tk.Label(opts, text="Engine:").grid(row=0, column=0, sticky="w")
        self.engine_var = tk.StringVar(value="kneejerk")
        tk.OptionMenu(opts, self.engine_var, *engine_names()).grid(row=0, column=1, sticky="w")

        tk.Label(opts, text="Colour:").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.color_var = tk.StringVar(value="black")
        tk.OptionMenu(opts, self.color_var, "black", "white", "random").grid(
            row=0, column=3, sticky="w")

        tk.Label(opts, text="Mode:").grid(row=1, column=0, sticky="w")
        self.rated_var = tk.BooleanVar(value=False)
        tk.Radiobutton(opts, text="Casual", variable=self.rated_var,
                       value=False).grid(row=1, column=1, sticky="w")
        tk.Radiobutton(opts, text="Rated", variable=self.rated_var,
                       value=True).grid(row=1, column=2, sticky="w")

        tk.Label(opts, text="Time:").grid(row=2, column=0, sticky="w")
        self.preset_var = tk.StringVar(value=TIME_PRESETS[3][0])
        tk.OptionMenu(opts, self.preset_var, *[p[0] for p in TIME_PRESETS]).grid(
            row=2, column=1, columnspan=2, sticky="w")

        # Opponent list
        box = tk.LabelFrame(self.win, text="Online bots to challenge", padx=6, pady=6)
        box.pack(fill="both", expand=True, **pad)
        listrow = tk.Frame(box)
        listrow.pack(fill="both", expand=True)
        scroll = tk.Scrollbar(listrow)
        scroll.pack(side="right", fill="y")
        self.bot_list = tk.Listbox(listrow, height=8, yscrollcommand=scroll.set)
        self.bot_list.pack(side="left", fill="both", expand=True)
        self.bot_list.bind("<<ListboxSelect>>", self._on_pick_bot)
        scroll.config(command=self.bot_list.yview)

        oppo = tk.Frame(box)
        oppo.pack(fill="x", pady=(4, 0))
        tk.Label(oppo, text="Opponent:").pack(side="left")
        self.opponent_var = tk.StringVar()
        tk.Entry(oppo, textvariable=self.opponent_var, width=20).pack(side="left", padx=4)
        tk.Button(oppo, text="Refresh list", command=self._refresh_bots).pack(side="right")

        # Action buttons
        act = tk.Frame(self.win)
        act.pack(fill="x", **pad)
        self.play_btn = tk.Button(act, text="Challenge & Play", command=self._challenge)
        self.play_btn.pack(side="left")
        self.stop_btn = tk.Button(act, text="Resign / Stop", command=self._stop,
                                  state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        # Log
        self.log_text = tk.Text(self.win, height=7, width=54, state="disabled")
        self.log_text.pack(fill="both", expand=True, **pad)

    # --- settings --------------------------------------------------------
    def _apply_settings(self) -> None:
        s = self.settings
        self.token_var.set(s.get("token", ""))
        self.engine_var.set(s.get("engine", "kneejerk"))
        self.color_var.set(s.get("color", "black"))
        self.rated_var.set(bool(s.get("rated", False)))
        # Match a preset to the saved clock if we can.
        for label, minutes, inc in TIME_PRESETS:
            if abs(minutes - s.get("clock_limit_min", 3.0)) < 1e-6 \
                    and inc == s.get("clock_increment", 2):
                self.preset_var.set(label)
                break

    def _collect_settings(self) -> dict:
        minutes, inc = self._current_clock()
        return {
            "token": self.token_var.get().strip(),
            "engine": self.engine_var.get(),
            "color": self.color_var.get(),
            "rated": bool(self.rated_var.get()),
            "clock_limit_min": minutes,
            "clock_increment": inc,
        }

    def _current_clock(self):
        for label, minutes, inc in TIME_PRESETS:
            if label == self.preset_var.get():
                return minutes, inc
        return 3.0, 2

    def _save(self) -> None:
        self.settings = self._collect_settings()
        save_settings(self.settings)
        self._log("Settings saved.")

    def _on_close(self) -> None:
        self.stop_flag.set()
        self._save()
        self.win.destroy()

    # --- helpers ---------------------------------------------------------
    def _log(self, message: str) -> None:
        def append():
            self.log_text.config(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(0, append)

    def _client_or_log(self) -> Optional[LichessClient]:
        token = self.token_var.get().strip()
        if not token:
            self._log("Enter your Lichess bot API token first.")
            return None
        return LichessClient(token)

    def _on_pick_bot(self, _event=None) -> None:
        sel = self.bot_list.curselection()
        if sel:
            name = self.bot_list.get(sel[0]).split()[-1]
            self.opponent_var.set(name)

    # --- network actions (each on its own thread) ------------------------
    def _verify(self) -> None:
        client = self._client_or_log()
        if client is None:
            return

        def work():
            try:
                acct = client.account()
                title = acct.get("title", "")
                tag = f"{title} " if title else ""
                self._log(f"Logged in as {tag}{acct.get('username', '?')}.")
                if acct.get("title") != "BOT":
                    self._log("Warning: this is not a BOT account; bot play will fail. "
                              "Upgrade it via the Lichess bot API.")
            except LichessError as exc:
                self._log(f"Verify failed: {exc}")

        threading.Thread(target=work, daemon=True).start()

    def _refresh_bots(self) -> None:
        client = self._client_or_log()
        if client is None:
            return
        self._log("Fetching online bots…")

        def work():
            try:
                bots = client.online_bots(50)
            except LichessError as exc:
                self._log(f"Could not fetch bots: {exc}")
                return

            def fill():
                self.bot_list.delete(0, "end")
                for bot in bots:
                    self.bot_list.insert("end", f"{bot['title']} {bot['username']}")
            self.root.after(0, fill)
            self._log(f"Found {len(bots)} online bots.")

        threading.Thread(target=work, daemon=True).start()

    def _challenge(self) -> None:
        if self.playing:
            self._log("A game is already in progress.")
            return
        client = self._client_or_log()
        if client is None:
            return
        opponent = self.opponent_var.get().strip()
        if not opponent:
            self._log("Pick or type an opponent bot first.")
            return

        self.client = client
        self.stop_flag.clear()
        self.playing = True
        self.play_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self._save()  # persist choices when starting a game

        minutes, inc = self._current_clock()
        engine = get_engine(self.engine_var.get())
        params = dict(
            opponent=opponent,
            rated=bool(self.rated_var.get()),
            clock_limit=int(minutes * 60),
            clock_increment=int(inc),
            color=self.color_var.get(),
            engine=engine,
        )
        threading.Thread(target=self._run_game, kwargs=params, daemon=True).start()

    def _stop(self) -> None:
        self.stop_flag.set()
        if self.client and self.game_id:
            try:
                self.client.resign(self.game_id)
            except LichessError:
                pass
        self._log("Stopping game…")

    # --- the game loop ---------------------------------------------------
    def _run_game(self, *, opponent, rated, clock_limit, clock_increment,
                  color, engine) -> None:
        try:
            account = self.client.account()
            our_id = account.get("username", "").lower()
            self._log(f"Challenging {opponent} ({'rated' if rated else 'casual'}, "
                      f"{clock_limit // 60}+{clock_increment})…")
            self.client.create_challenge(
                opponent, rated=rated, clock_limit=clock_limit,
                clock_increment=clock_increment, color=color)

            game_id = self._await_game_start()
            if game_id is None:
                return
            self.game_id = game_id
            self._log(f"Game started: {game_id}")
            self._play_game(game_id, our_id, engine)
        except LichessError as exc:
            self._log(f"Lichess error: {exc}")
        except Exception as exc:  # noqa: BLE001 - never kill the GUI thread silently
            self._log(f"Unexpected error: {exc}")
        finally:
            self._finish_game()

    def _await_game_start(self) -> Optional[str]:
        for event in self.client.stream_events():
            if self.stop_flag.is_set():
                return None
            if event.get("type") == "gameStart":
                game = event.get("game", {})
                return game.get("gameId") or game.get("id")
            if event.get("type") == "challengeDeclined":
                self._log("Challenge was declined.")
                return None
        return None

    def _play_game(self, game_id: str, our_id: str, engine) -> None:
        our_color: Optional[bool] = None
        initial_fen = None

        for event in self.client.stream_game(game_id):
            if self.stop_flag.is_set():
                return
            etype = event.get("type")
            if etype == "gameFull":
                white = event.get("white", {}).get("id", "").lower()
                our_color = chess.WHITE if white == our_id else chess.BLACK
                fen = event.get("initialFen", "startpos")
                initial_fen = None if fen in ("startpos", "", None) else fen
                self._log("Playing as " + ("White" if our_color else "Black") + ".")
                state = event.get("state", {})
            elif etype == "gameState":
                state = event
            else:
                continue

            board = self._board_from(initial_fen, state.get("moves", ""))
            self._show_board(board, our_color)

            status = state.get("status", "started")
            if status not in ("started", "created"):
                self._log(f"Game over: {status}"
                          + (f" ({state.get('winner')} wins)" if state.get("winner") else ""))
                return

            if board.turn == our_color and not board.is_game_over():
                self._make_engine_move(game_id, board, engine, state)

    def _make_engine_move(self, game_id, board, engine, state) -> None:
        limits = TimeLimits(
            wtime=_sec(state.get("wtime")),
            btime=_sec(state.get("btime")),
            winc=_sec(state.get("winc")) or 0.0,
            binc=_sec(state.get("binc")) or 0.0,
        )
        move = harness.safe_choose(engine, board, limits)
        if move is None:
            return
        narration = getattr(engine, "narration", "")
        note = f" ({narration})" if narration else ""
        try:
            self.client.make_move(game_id, move.uci())
            self._log(f"{engine.name} played {move.uci()}{note}")
        except LichessError as exc:
            self._log(f"Move rejected: {exc}")

    @staticmethod
    def _board_from(initial_fen, moves_str) -> chess.Board:
        board = chess.Board(initial_fen) if initial_fen else chess.Board()
        for token in moves_str.split():
            try:
                board.push_uci(token)
            except ValueError:
                break
        return board

    def _show_board(self, board: chess.Board, our_color) -> None:
        def update():
            self.app.board = board.copy()
            self.app.human_color = our_color if our_color is not None else chess.WHITE
            self.app.last_move = board.peek() if board.move_stack else None
            self.app.lichess_active = True
            self.app.redraw()
        self.root.after(0, update)

    def _finish_game(self) -> None:
        self.playing = False
        self.game_id = None

        def reset():
            self.play_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.app.lichess_active = False
        self.root.after(0, reset)


def _sec(ms):
    return None if ms is None else ms / 1000.0
