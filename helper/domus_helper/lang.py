"""The User wants Ashley (and any agent on Domus) to understand Sims' social talk the way the Sentient Sims mod does: in plain sentences instead of tuning names. Sentient Sims (public repo guspuffygit/sentient-sims-app, MIT-labelled) keeps a hand-written dictionary, src/main/sentient-sims/descriptions/interactionDescriptions.ts: ~1,540 social interactions, each mapped to sentence templates with actor slots, e.g. a key like mixer_social_Example_targeted with pre_actions: ['{actor.0} is asking {actor.1} about their day.'], plus ~400 keys marked ignored: true (too dull to narrate).

Domus already sees the same tuning names: the portrait's addressed list (domus_helper/thalamus/observation.py: {"by": actor_id, "interaction": _affordance_name(text)}), and her own running/queued interactions in the same portrait. This lane adds a sentence beside those names when the dictionary has one.

The phrase data is Sentient Sims' (MIT, guspuffygit/sentient-sims-app); it is imported locally and never committed. Attribution travels inside the data file.
"""
import argparse
import json
import re
import time
from datetime import date
from pathlib import Path

from .paths import Paths

_START = re.compile(
    "^    (?:'((?:\\\\'|[^'])*)'|\"((?:\\\\\"|[^\"])*)\"|([A-Za-z_][A-Za-z0-9_-]*))\\s*:\\s*\\{",
    re.M)
_IGNORED = re.compile(r"ignored\s*:\s*true\b")
_PRE_OPEN = re.compile(r"pre_actions\s*:\s*\[")
_ACTOR = re.compile(r"\{actor\.(\d+)\}")
_SPACE = re.compile(r"\s+")
_SENTENCE_CAP = 200
_RELOAD_S = 60

_cached = None
_cached_mtime = None
_checked_at = None


def _unescape_key(text):
    return text.replace("\\'", "'").replace('\\"', '"')


def _body_after(text, open_brace):
    """Inner text of the object whose '{' sits at open_brace. Strings are opaque."""
    i = open_brace + 1
    depth = 1
    quote = None
    while i < len(text) and depth:
        char = text[i]
        if quote:
            if char == "\\" and i + 1 < len(text):
                i += 2
                continue
            if char == quote:
                quote = None
            i += 1
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1:i]
        i += 1
    return text[open_brace + 1:]


def _single_quoted(text):
    found = []
    i = 0
    limit = len(text)
    while i < limit:
        if text[i] != "'":
            i += 1
            continue
        i += 1
        chars = []
        while i < limit:
            if text[i] == "\\" and i + 1 < limit and text[i + 1] == "'":
                chars.append("'")
                i += 2
                continue
            if text[i] == "'":
                i += 1
                break
            chars.append(text[i])
            i += 1
        found.append("".join(chars))
    return found


def _pre_actions(body):
    match = _PRE_OPEN.search(body)
    if match is None:
        return None
    i = match.end()
    depth = 1
    start = i
    quote = None
    while i < len(body) and depth:
        char = body[i]
        if quote:
            if char == "\\" and i + 1 < len(body):
                i += 2
                continue
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return _single_quoted(body[start:i])
        i += 1
    return _single_quoted(body[start:])


def import_descriptions(ts_path, out_path, source):
    """Parse a Sentient Sims descriptions file by regex (never eval) and write social.json."""
    text = Path(ts_path).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    entries = {}
    for match in _START.finditer(text):
        raw = next(group for group in match.groups() if group is not None)
        key = _unescape_key(raw).lower()
        body = _body_after(text, match.end() - 1)
        if _IGNORED.search(body):
            entries[key] = {"ignored": True}
            continue
        phrases = _pre_actions(body)
        if phrases:
            entries[key] = {"pre": phrases}
    payload = {"v": 1, "source": source, "entries": entries}
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"pre": sum(1 for item in entries.values() if "pre" in item),
            "ignored": sum(1 for item in entries.values() if item.get("ignored") is True)}


def _fill(template, actors):
    def repl(match):
        index = int(match.group(1))
        if isinstance(actors, (list, tuple)) and index < len(actors):
            name = actors[index]
            if isinstance(name, str) and name:
                return name
        return "someone"
    text = _SPACE.sub(" ", _ACTOR.sub(repl, template)).strip()
    return text[:_SENTENCE_CAP]


class SocialPhrases:
    def __init__(self, entries):
        self.entries = entries

    @classmethod
    def load(cls, path):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            entries = data.get("entries") if isinstance(data, dict) else None
            if not isinstance(entries, dict):
                entries = {}
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, AttributeError):
            entries = {}
        return cls(entries)

    def sentence(self, tuning_name, actors):
        if not isinstance(tuning_name, str):
            return None
        entry = self.entries.get(tuning_name.lower())
        if not isinstance(entry, dict) or entry.get("ignored") is True:
            return None
        pre = entry.get("pre")
        if not isinstance(pre, list) or not pre or not isinstance(pre[0], str):
            return None
        return _fill(pre[0], actors)


def phrases():
    """The data-dir dictionary, loaded once and refreshed when the file changes."""
    global _cached, _cached_mtime, _checked_at
    now = time.monotonic()
    if _cached is not None and _checked_at is not None and now - _checked_at < _RELOAD_S:
        return _cached
    path = Paths.from_env().data_dir / "lang" / "social.json"
    _checked_at = now
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        mtime = None
    if _cached is None or mtime != _cached_mtime:
        _cached = SocialPhrases.load(path)
        _cached_mtime = mtime
    return _cached


def _social_path():
    return Paths.from_env().data_dir / "lang" / "social.json"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.lang")
    sub = parser.add_subparsers(dest="cmd", required=True)
    incoming = sub.add_parser("import")
    incoming.add_argument("ts_path")
    incoming.add_argument("--repo", required=True)
    incoming.add_argument("--path", required=True)
    incoming.add_argument("--commit", required=True)
    shown = sub.add_parser("show")
    shown.add_argument("tuning_name")
    args = parser.parse_args(argv)
    if args.cmd == "import":
        source = {"repo": args.repo, "path": args.path, "commit": args.commit,
                  "license": "MIT", "fetched": date.today().isoformat()}
        print(json.dumps(import_descriptions(args.ts_path, _social_path(), source)))
        return 0
    entry = phrases().entries.get(str(args.tuning_name).lower())
    print(json.dumps(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
