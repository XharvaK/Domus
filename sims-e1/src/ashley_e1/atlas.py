"""Chunked interaction-tuning dump. No game imports."""

import json
import os
import time

from . import schema
from .writer import append_atlas_line


def _missing(read):
    try:
        return read()
    except AttributeError:
        return None


def _bool_or_null(value):
    if type(value) is bool:
        return value
    return None


def _enum_name(value):
    if value is None:
        return None
    try:
        name = value.name
    except AttributeError:
        return None
    if type(name) is not str:
        return None
    if len(name) > 128:
        return name[:128]
    return name


def _static_commodities(value):
    if type(value) not in (list, tuple):
        return None
    guids = []
    for entry in value:
        try:
            commodity = entry.static_commodity
        except AttributeError:
            commodity = None
        source = entry if commodity is None else commodity
        try:
            guid = source.guid64
        except AttributeError:
            guid = None
        if type(guid) is int:
            guids.append(guid)
    return sorted(set(guids))[:32]


def _number(value):
    if type(value) in (int, float):
        return value
    return None


def _ad_stat(ad_list):
    stat = _missing(lambda: ad_list._stat_type)
    guid = _missing(lambda: stat.guid64)
    name = _missing(lambda: stat.__name__)
    return (guid if type(guid) is int else None,
            name[:64] if type(name) is str else None)


def _ad_ops(ad_list):
    ops = []
    try:
        listed = list(_missing(lambda: ad_list._op_list) or ())
    except TypeError:
        return ops
    for op in listed[:4]:
        name = type(op).__name__
        ops.append({
            "op": name[:48],
            "amount": _number(_missing(lambda: op._amount)),
            "advertise": _bool_or_null(_missing(lambda: op._advertise)),
        })
    return ops


def _autonomy_ads(value):
    """DA6G: what the game says an interaction does to each statistic. Bytecode
    (interactions/base/interaction, utils/autonomy_op_list, statistics/statistic_ops):
    Interaction._autonomy_ads maps a stat type to an AutonomyAdList whose _stat_type
    and _op_list are plain attributes; an op's _amount and _advertise are set in
    __init__. Nothing here calls a method on them."""
    if value is None:
        return None
    try:
        lists = list(value.values())
    except (AttributeError, TypeError):
        return None
    ads = []
    for ad_list in lists:
        guid, name = _ad_stat(ad_list)
        ads.append({"stat": guid, "name": name, "ops": _ad_ops(ad_list)})
    ads.sort(key=lambda ad: (ad["name"] or "", ad["stat"] or 0))
    return ads[:16]


def _affordance_row(cls):
    guid = _missing(lambda: cls.guid64)
    name = _missing(lambda: cls.__name__)
    if type(name) is not str:
        name = None
    elif len(name) > 128:
        name = name[:128]
    posture = _missing(lambda: cls.posture_preferences)
    return {
        "kind": "affordance",
        "guid64": guid if type(guid) is int else None,
        "name": name,
        "is_super": _bool_or_null(_missing(lambda: cls.is_super)),
        "is_social": _bool_or_null(_missing(lambda: cls.is_social)),
        "target_type": _enum_name(_missing(lambda: cls.target_type)),
        "allow_autonomous": _bool_or_null(_missing(lambda: cls.allow_autonomous)),
        "allow_user_directed": _bool_or_null(_missing(lambda: cls.allow_user_directed)),
        "require_current_posture": _bool_or_null(_missing(lambda: cls._require_current_posture)),
        "posture_preferences": None if posture is None else type(posture).__name__,
        "static_commodities": _static_commodities(_missing(lambda: cls._static_commodities)),
        "autonomy_ads": _autonomy_ads(_missing(lambda: cls._autonomy_ads)),
    }


class AtlasDump(object):
    def __init__(self, manager_types, out_path, budget_ms=5.0, max_per_chunk=200,
                 clock=time.perf_counter):
        self._keys = sorted(manager_types.keys(), key=str)
        self._types = manager_types
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
            "kind": "atlas_header",
            "probe_version": schema.PROBE_VERSION,
            "sims_build": schema.SIMS_BUILD,
            "total": len(self._keys),
            "started_ms": int(time.time() * 1000),
        }
        append_atlas_line(self.partial, _line(header))

    def step(self):
        if self.state != "running":
            return
        start = self.clock()
        processed = 0
        while self._index < len(self._keys):
            if processed >= self.max_per_chunk:
                break
            if (self.clock() - start) * 1000.0 >= self.budget_ms:
                break
            key = self._keys[self._index]
            self._index += 1
            processed += 1
            try:
                row = _affordance_row(self._types[key])
                self._count += 1
            except Exception as error:
                row = {"kind": "affordance_error", "key": str(key)[:128],
                       "error": type(error).__name__}
                self._errors += 1
            append_atlas_line(self.partial, _line(row))
        self.chunks += 1
        self._chunk_ms.append((self.clock() - start) * 1000.0)
        if self._index >= len(self._keys):
            self._finish()

    def _finish(self):
        ordered = sorted(self._chunk_ms)
        footer = {
            "kind": "atlas_footer",
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
            "total": len(self._keys),
            "chunks": self.chunks,
            "max_chunk_ms": max(self._chunk_ms) if self._chunk_ms else 0,
            "file": path,
        }


def _line(row):
    return json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
