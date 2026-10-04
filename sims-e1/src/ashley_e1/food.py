"""Chunked read of food affordances and one crafting menu per object.

No game imports. The probe supplies a runner. Rows stay partial until the footer.
"""
import json
import os
import time

from . import schema
from .writer import append_atlas_line

NAME_PARTS = ("cook", "snack", "leftover", "eat", "grab", "serving", "meal", "drink")
FOOD_GUIDS = (13388, 13397)
MENU_CAP = 200


def name_hit(name, guid):
    if guid in FOOD_GUIDS:
        return True
    text = name.lower() if type(name) is str else ""
    return any(part in text for part in NAME_PARTS)


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
