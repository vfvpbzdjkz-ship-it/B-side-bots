# RETRO ROSTER — B-Side Engines

Five earnest, lightweight chess engines, each built around an old, outdated, or
proof-of-concept idea. None are *intentionally* bad — every one tries its best;
they're just charmingly limited. All ship as **UCI** engines, run on the
**lichess-bot** bridge, and share a single safety-first harness.

| Engine     | Primary system                                               | Era / origin                                  | Difficulty |
|------------|--------------------------------------------------------------|-----------------------------------------------|------------|
| TURAMPION  | Point-count eval + "dead-position" (proto-quiescence) search | Turochamp, 1948 (homage)                      | Low-Med    |
| SHANNSTEIN | Selective forward pruning — search only *plausible* moves    | Shannon Type-B 1950 + Bernstein 1957 (fusion) | Low-Med    |
| COPYBOOK   | Prioritized if-then rule cascade (symbolic expert system)    | 1950s–60s rule-based AI                       | Low        |
| KNEEJERK   | 1-ply tapered piece-square eval (intuition, no lookahead)    | Proof of concept                              | Very Low   |
| BEELINE    | King-tropism eval (pieces gain value near the enemy king)    | Classic eval-term gimmick                     | Low-Med    |

## Design — one harness, five strategies

Every engine differs *only* in how it picks a move. UCI handling, time budgeting,
the legal-move safety net, and the random tiebreak are shared, so a bug fixed once
is fixed everywhere. Each engine implements the same tiny interface:

```python
class Engine:
    name: str
    author: str
    def new_game(self) -> None: ...                # optional per-game reset
    def choose_move(self, board, limits) -> chess.Move: ...
```

The UCI driver picks which engine to load from the `ENGINE` environment variable
(or `--engine` flag), so each gets its own lichess-bot config pointed at the same
program with a different flag.

## Layout

```
retro/
  uci.py              UCI stdin/stdout driver (shared)
  harness.py          safety wrapper: always legal, in time, never crashes
  timeman.py          TimeLimits + budgeting
  gui.py              Tkinter graphical board (play any engine)
  common/
    evalutil.py       material values, tapered PeSTO PST eval, game-phase
    tactics.py        mate_in_1, is_hanging, see_gain (approx SEE)
    moveutil.py       plausibility scoring, random tiebreak, helpers
  engines/
    turampion.py  shannstein.py  copybook.py  kneejerk.py  beeline.py
lichess-bot/          ready-to-use wrappers + config for the Lichess bridge
tests/                perft, safety battery, eval, tactics, per-engine behavior
run.sh / run.bat      launch the UCI driver (ENGINE selects the strategy)
RetroRoster.pyw       double-click on Windows to open the GUI
config.json           per-engine knobs / roster description
```

## Requirements

- Python 3.11+
- `python-chess` and `pytest` (`pip install -r requirements.txt`)
- No numpy. Tkinter (bundled with most Python installs) only for the optional GUI.

## Running an engine (UCI)

```bash
pip install -r requirements.txt
ENGINE=copybook ./run.sh          # or run.bat on Windows; defaults to kneejerk
```

Then talk UCI to it, or load it in a GUI like **Cute Chess** as a UCI engine.
Quick manual check:

```bash
printf 'uci\nposition startpos\ngo movetime 500\nquit\n' | ENGINE=beeline ./run.sh
```

COPYBOOK additionally narrates the rule it fired, e.g.
`info string rule 6: develop a knight`.

## Graphical interface (play against any engine)

A small Tkinter board is included — pick an engine from the dropdown and play:

```bash
python3 -m retro.gui
```

On **Windows** just double-click **`RetroRoster.pyw`** (or `Launch-RetroRoster.bat`)
to open the board with no console window. Click a piece, then its destination;
pawn promotions auto-queen. The status bar shows the engine's move and COPYBOOK's
rule narration.

### Building a standalone Windows `.exe`

To hand someone a single double-clickable executable with nothing else to install,
run **`build_windows_exe.bat`** on a Windows machine with Python. It uses
PyInstaller to bundle everything into `dist\RetroRoster.exe`. (A compiled binary
isn't committed to the repo; you build it from source with that script.)

## Playing on Lichess

The engines plug straight into the [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot)
bridge. See [`lichess-bot/README.md`](lichess-bot/README.md): copy the example
config, point it at the wrapper for the engine you want (`lichess-bot/engines/retro-<name>`),
add your bot token, and run. Run five accounts to put the whole roster online at once.

## The engines

- **TURAMPION** — a point-count evaluation (material, mobility via `√moves`, piece
  safety, king safety, castling, pawn advancement, check/mate threats) scored after
  a *dead-position* search that follows captures, recaptures and brief checks until
  the position is quiet. Proto-quiescence, decades early. Plays like a thoughtful
  Victorian beginner.
- **SHANNSTEIN** — negamax alpha-beta that, at every node, scores moves with a cheap
  `plausibility` heuristic and recurses only on the top-K (Bernstein's ~7). Fast and
  pointed — and authentically prunes away the real best move when the heuristic
  misses it. Always keeps *all* moves when there are fewer than K.
- **COPYBOOK** — a prioritized cascade of ten if-then maxims (mate, escape check,
  safe capture, save a hanging piece, castle, develop a minor knights-first, stake a
  center pawn, rook to an open file, improve the worst piece, safe waiting move).
  No search tree; each candidate passes a 1-ply safety veto. It explains itself.
- **KNEEJERK** — pure positional intuition: try every move, statically score the
  result with the tapered PeSTO eval, play the best. Zero lookahead; the cleanest
  illustration of "what evaluation alone buys you."
- **BEELINE** — material + tapered PST + a *king-tropism* term (every piece gains
  value near the enemy king, plus king-ring attacker and check bonuses), driven by a
  shallow 2–3 ply alpha-beta so it attacks without simply donating material.

## Safety guarantees (the harness)

`harness.safe_choose` guarantees every engine, no matter how it misbehaves:

- returns a **legal** move (random-legal fallback on any error or illegal return),
- never runs past its time budget (cooperative deadline + a hard worker-thread
  deadline), so it never flags on Lichess,
- never crashes the process.

## Testing

```bash
pytest
```

- `test_perft.py` — python-chess movegen sanity (start position to depth 4).
- `test_safety.py` — **critical, runs against every engine**: over a battery of
  positions each engine returns a legal move within budget and never raises; forced
  exceptions, illegal returns, and runaway searches all hit the fallback.
- `test_evalutil.py` — tapered eval is color-symmetric; phase hits middlegame at full
  material and endgame with bare kings.
- `test_tactics.py` — `mate_in_1`, `is_hanging`, `see_gain` on hand-built positions.
- `test_engines.py` — per-engine character: TURAMPION wins a free exchange via the
  dead search, SHANNSTEIN keeps all moves under K, COPYBOOK plays the mate and
  narrates rule 1, KNEEJERK develops on move 1, BEELINE steers toward the king.

## Credits

Evaluation uses the public-domain **PeSTO** piece-square tables (Ronald Friederich /
RofChade). Chess rules and move generation are provided by `python-chess`; all
evaluation and move-choice logic here is original.
