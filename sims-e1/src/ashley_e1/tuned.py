"""Chunked class-tuning scan of lot objects. No game imports."""

import json
import os
import time

from . import schema
from .writer import append_atlas_line


def _descriptor(value):
    for klass in type(value).__mro__:
        if "__get__" in klass.__dict__:
            return True
    return False


def _plain(obj, name, instance):
    for klass in type(obj).__mro__:
        if name not in klass.__dict__:
            continue
        value = klass.__dict__[name]
        if _descriptor(value):
            continue
        return value
    if not instance:
        return None
    try:
        raw = obj.__dict__
    except AttributeError:
        return None
    if type(raw) is not dict or name not in raw:
        return None
    value = raw[name]
    if _descriptor(value):
        return None
    return value


def _class_plain(cls, name):
    if isinstance(cls, type):
        for klass in cls.__mro__:
            if name not in klass.__dict__:
                continue
            value = klass.__dict__[name]
            if _descriptor(value):
                continue
            return value
        return None
    return _plain(cls, name, True)


def _int_or_null(value):
    if type(value) is int:
        return value
    return None


def _row(obj):
    found = _plain(obj, "id", True)
    object_id = None if _int_or_null(found) is None else str(found)
    definition = _plain(obj, "definition", True)
    definition_id = None
    if definition is not None:
        definition_id = _int_or_null(_plain(definition, "id", True))
    name = type(obj).__name__
    if type(name) is not str:
        name = ""
    elif len(name) > 128:
        name = name[:128]
    sim = _plain(obj, "is_sim", False)
    if type(sim) is not bool:
        sim = None
    tuned = _plain(obj, "_super_affordances", False)
    guids = []
    if type(tuned) in (list, tuple, frozenset, set):
        for affordance in tuned:
            guid = _int_or_null(_class_plain(affordance, "guid64"))
            if guid is not None:
                guids.append(guid)
    unique = sorted(set(guids))
    return {
        "kind": "tuned_on_class",
        "object_id": object_id,
        "definition_id": definition_id,
        "class_name": name,
        "is_sim": sim,
        "affordance_guid64s": unique[:64],
        "truncated": len(unique) > 64,
    }


class TunedScan(object):
    def __init__(self, objects_snapshot, out_path, budget_ms=5.0, max_per_chunk=50,
                 max_objects=500, clock=time.perf_counter):
        self._objects = list(objects_snapshot)[:max_objects]
        self.out_path = out_path
        self.partial = out_path + ".partial"
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
            "kind": "tuned_header",
            "probe_version": schema.PROBE_VERSION,
            "sims_build": schema.SIMS_BUILD,
            "total": len(self._objects),
            "started_ms": int(time.time() * 1000),
        }
        append_atlas_line(self.partial, _line(header))

    def step(self):
        if self.state != "running":
            return
        start = self.clock()
        processed = 0
        while self._index < len(self._objects):
            if processed >= self.max_per_chunk:
                break
            if (self.clock() - start) * 1000.0 >= self.budget_ms:
                break
            obj = self._objects[self._index]
            self._index += 1
            processed += 1
            try:
                row = _row(obj)
                self._count += 1
            except Exception as error:
                try:
                    found = _plain(obj, "id", True)
                    object_id = None if type(found) is not int else str(found)
                except Exception:
                    object_id = None
                row = {"kind": "tuned_error", "object_id": object_id,
                       "error": type(error).__name__}
                self._errors += 1
            append_atlas_line(self.partial, _line(row))
        self.chunks += 1
        self._chunk_ms.append((self.clock() - start) * 1000.0)
        if self._index >= len(self._objects):
            self._finish()

    def _finish(self):
        ordered = sorted(self._chunk_ms)
        footer = {
            "kind": "tuned_footer",
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
        if self.state == "done":
            path = self.out_path
        elif self.state == "idle":
            path = None
        else:
            path = self.partial
        return {
            "state": self.state,
            "done": self._index,
            "total": len(self._objects),
            "chunks": self.chunks,
            "max_chunk_ms": max(self._chunk_ms) if self._chunk_ms else 0,
            "file": path,
        }


def _line(row):
    return json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
