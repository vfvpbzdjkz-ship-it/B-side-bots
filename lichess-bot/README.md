# Running RETRO ROSTER on lichess-bot

The engines already speak **UCI** over stdin/stdout, so they drop straight into
the [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot) bridge — no
bespoke Lichess event loop, exactly as the build spec requires.

## How it fits together

```
lichess-bot  ──spawns──▶  lichess-bot/engines/retro-<name>  ──exec──▶  python -m retro.uci   (ENGINE=<name>)
```

`engines/retro-<name>` is a one-line wrapper that launches the shared UCI driver
with the right `ENGINE` selected. There is one wrapper per engine, for POSIX
(`retro-beeline`) and Windows (`retro-beeline.bat`):

- `retro-turampion`
- `retro-shannstein`
- `retro-copybook`
- `retro-kneejerk`
- `retro-beeline`
- `retro-mirror`  (mirrors its opponent; best deployed as a Black-only bot)

## Setup

1. Install this repo's dependency so the driver can import it:
   ```
   pip install -r requirements.txt
   ```
2. Clone lichess-bot and install its own requirements:
   ```
   git clone https://github.com/lichess-bot-devs/lichess-bot
   cd lichess-bot
   pip install -r requirements.txt
   ```
3. Create a **bot** account on Lichess and an API token with the
   `bot:play` scope (`https://lichess.org/account/oauth/token`). Upgrade the
   account to a bot account per lichess-bot's instructions.
4. Copy `config.example.yml` from this folder to lichess-bot's `config.yml` and:
   - paste your token,
   - set `engine.dir` to the **absolute** path of this repo's
     `lichess-bot/engines` folder,
   - set `engine.name` to the wrapper you want (e.g. `retro-copybook`, or
     `retro-copybook.bat` on Windows).
5. Start the bridge:
   ```
   python3 lichess-bot.py
   ```

## Running the whole roster at once

Make five bot accounts, copy `config.example.yml` five times, and change
`token` + `engine.name` in each — then run five lichess-bot processes. Each one
is a different personality pointed at the same program.

## Sanity check a wrapper locally

```
printf 'uci\nposition startpos\ngo movetime 500\nquit\n' | ./engines/retro-beeline
```

You should see `id name BEELINE`, `uciok`, and a `bestmove`.
