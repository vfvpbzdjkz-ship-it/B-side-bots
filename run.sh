#!/usr/bin/env bash
# Launch the RETRO ROSTER UCI driver. The ENGINE env var selects the strategy,
# e.g. `ENGINE=copybook ./run.sh`. Defaults to kneejerk.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m retro.uci "$@"
