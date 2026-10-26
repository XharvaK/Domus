"""Chunked read of food affordances and one crafting menu per object.

No game imports. The probe supplies a runner. Rows stay partial until the footer.
"""
import json
import os
import time

from . import schema
from .writer import append_atlas_line

NAME_PARTS = ("cook", "snack", "leftover", "eat", "grab", "serving", "meal", "drink",
              "consume")
# D35 (live 2026-10-04): a served plate is eaten through generic_consume_food;
# "consum" also hit utilities_AddUtility_PowerConsumption.
# D21 (live 2026-10-04): a substring "eat" matched cheat, death and create (401 of
# 701 scanned rows). A part must begin a word of the tuning name.
FOOD_GUIDS = (13388, 13397)
MENU_CAP = 200


def _words(name):
    """Split on case changes, digits and separators: GrabSnack_8Servings ->
    grab, snack, 8, servings; BBQMeal -> bbq, meal."""
    words = []
    current = ""
    for index, char in enumerate(name):
        if not char.isalnum():
            kind = None
        elif char.isdigit():
            kind = "digit"
        elif char.isupper():
            kind = "upper"
        else:
            kind = "lower"
        last = current[-1:] if current else ""
        if kind is None:
            split = True
        elif not current:
            split = False
        elif kind == "digit":
            split = not last.isdigit()
        elif last.isdigit():
            split = True
        elif kind == "upper":
            split = last.islower()
        else:
            # An upper run followed by lower: the run's last letter starts the word.
            split = False
            if len(current) > 1 and last.isupper() and current[-2].isupper():
                words.append(current[:-1])
                current = last
        if split and current:
            words.append(current)
            current = ""
        if kind is not None:
            current += char
    if current:
        words.append(current)
    return [word.lower() for word in words]


def name_hit(name, guid):
    if guid in FOOD_GUIDS:
        return True
    words = _words(name) if type(name) is str else []
    return any(word.startswith(part) for word in words for part in NAME_PARTS)


class FoodScan(object):
    def __init__(self, jobs, out_path, runner, budget_ms=5.0, max_per_chunk=50,
                 clock=time.perf_counter):
        self._jobs = list(jobs)
        self.out_path = out_path
        self.partial = out_path + ".partial"
        self._runner = runner
        self.budget_ms = budget_ms
        self.max_per_chunk = max_per_chunk
        self.clock = clock
        self.state = "running"
        self._index = 0
        self._count = 0
        self._errors = 0
        self.chunks = 0
        self._chunk_ms = []
        header = {
            "kind": "food_header",
            "probe_version": schema.PROBE_VERSION,
            "sims_build": schema.SIMS_BUILD,
            "total": len(self._jobs),
            "started_ms": int(time.time() * 1000),
        }
        append_atlas_line(self.partial, _line(header))

    def step(self):
        if self.state != "running":
            return
        start = self.clock()
        processed = 0
        while self._index < len(self._jobs):
            if processed >= self.max_per_chunk:
                break
            if (self.clock() - start) * 1000.0 >= self.budget_ms:
                break
            job = self._jobs[self._index]
            self._index += 1
            processed += 1
            try:
                produced = self._runner(job)
            except Exception as error:
                produced = [_error_row(job, error)]
            if type(produced) is not list:
                produced = [produced]
            for row in produced:
                if row.get("error"):
                    self._errors += 1
                else:
                    self._count += 1
                append_atlas_line(self.partial, _line(row))
        self.chunks += 1
        self._chunk_ms.append((self.clock() - start) * 1000.0)
        if self._index >= len(self._jobs):
            self._finish()

    def _finish(self):
        ordered = sorted(self._chunk_ms)
        footer = {
            "kind": "food_footer",
            "count": self._count,
            "errors": self._errors,
            "chunks": self.chunks,
            "max_chunk_ms": max(self._chunk_ms) if self._chunk_ms else 0,
            "p50_chunk_ms": ordered[(len(ordered) - 1) // 2] if ordered else 0,
        }
        append_atlas_line(self.partial, _line(footer))
        os.replace(self.partial, self.out_path)
        self.state = "done"

    def progress(self):
        """D22: the same shape as the atlas and tuned blocks on status."""
        if self.state == "done":
            path = self.out_path
        else:
            path = self.partial
        return {
            "state": self.state,
            "done": self._index,
            "total": len(self._jobs),
            "chunks": self.chunks,
            "max_chunk_ms": max(self._chunk_ms) if self._chunk_ms else 0,
            "file": path,
        }


def error_text(error):
    """D3: type and message, bounded. A bare type name needed another live round."""
    try:
        message = str(error)
    except Exception:
        message = ""
    text = type(error).__name__
    if message:
        text = "%s: %s" % (text, message)
    return text[:160]


def _error_row(job, error):
    kind = "food_menu" if job.get("menu") else "food_affordance"
    return {
        "kind": kind,
        "object_id": job.get("object_id"),
        "guid64": job.get("guid64"),
        "error": error_text(error),
    }



def _line(row):
    return json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
