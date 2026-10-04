"""Chunked preflight of the lot's tuned affordances. No game imports.

The probe supplies a runner that calls the actuator read. Rows stay partial
until the footer, same as a tuned scan.
"""
import json
import os
import time

from . import food
from . import schema
from .writer import append_atlas_line


class PreflightScan(object):
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
            "kind": "preflight_header",
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
                row = self._runner(job)
                self._count += 1
            except Exception as error:
                row = {
                    "kind": "preflight",
                    "object_id": job.get("object_id"),
                    "guid64": job.get("guid64"),
                    "name": job.get("name"),
                    "ok": False,
                    "reason": food.error_text(error),
                }
                self._errors += 1
            append_atlas_line(self.partial, _line(row))
        self.chunks += 1
        self._chunk_ms.append((self.clock() - start) * 1000.0)
        if self._index >= len(self._jobs):
            self._finish()

    def _finish(self):
        ordered = sorted(self._chunk_ms)
        footer = {
            "kind": "preflight_footer",
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


def _line(row):
    return json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
