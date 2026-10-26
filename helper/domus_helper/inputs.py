"""E1b: game-only inputs. The User can keep his conversations out of Ashley's game passes.

The switch lives in the helper's store and travels to Ashley in the heartbeat (inputs: game_only),
sent at once when it flips. Every flip is appended to inputs_log.jsonl in the data folder, which is
never rewritten. Run: python -m domus_helper.inputs game-only | full | show
"""
import argparse
import json
import time

from .paths import Paths
from .spool import Spool

GAME_ONLY = "game_only"
FULL = "full"
KEY = "inputs"
LOG = "inputs_log.jsonl"


def current(spool):
    return GAME_ONLY if spool.get_kv(KEY) == GAME_ONLY else FULL


def set_mode(spool, data_dir, mode, now_ms):
    if mode not in (GAME_ONLY, FULL):
        raise ValueError("inputs must be game_only or full")
    before = current(spool)
    spool.put_kv(KEY, mode)
    with open(data_dir / LOG, "a", encoding="utf-8") as log:
        log.write(json.dumps({"at_ms": now_ms, "inputs": mode, "before": before}, sort_keys=True) + "\n")
    return {"inputs": mode, "before": before}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.inputs")
    parser.add_argument("mode", choices=["game-only", "full", "show"])
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    spool = Spool(paths.data_dir / "spool.db")
    try:
        if args.mode == "show":
            print(json.dumps({"inputs": current(spool)}))
        else:
            mode = GAME_ONLY if args.mode == "game-only" else FULL
            print(json.dumps(set_mode(spool, paths.data_dir, mode, int(time.time() * 1000)), sort_keys=True))
        return 0
    finally:
        spool.close()


if __name__ == "__main__":
    raise SystemExit(main())
