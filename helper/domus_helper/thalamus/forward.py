"""Online forward models. Explicit state, no I/O."""

from domus_helper.calibration import _nearest_rank

_ALPHA = 0.2
_DURATION_CAP = 50


class NeedModel:
    """Rate of one motive under one activity, in value units per game tick."""

    def __init__(self):
        self.keys = {}

    def rate(self, motive, activity):
        slot = self.keys.get((motive, tuple(activity)))
        if slot is None or not slot["has_rate"]:
            return None
        return slot["rate"]

    def observe(self, motive, activity, ticks0, value0, ticks1, value1):
        """One consecutive pair. Returns z for the prediction that used the prior rate."""
        delta = ticks1 - ticks0
        rate_obs = (value1 - value0) / float(delta)
        key = (motive, tuple(activity))
        slot = self.keys.get(key)
        if slot is None or not slot["has_rate"]:
            self.keys[key] = {"rate": rate_obs, "sigma": 1.0, "has_rate": True}
            return 0.0
        predicted = value0 + slot["rate"] * delta
        error = value1 - predicted
        sigma = slot["sigma"] if slot["sigma"] > 1.0 else 1.0
        z = abs(error) / sigma
        slot["rate"] = slot["rate"] + _ALPHA * (rate_obs - slot["rate"])
        slot["sigma"] = slot["sigma"] + _ALPHA * (abs(error) - slot["sigma"])
        return z

    def reset(self):
        self.keys = {}

    def to_dict(self):
        encoded = []
        for (motive, activity), slot in self.keys.items():
            encoded.append({
                "motive": motive,
                "activity": list(activity),
                "rate": slot["rate"],
                "sigma": slot["sigma"],
                "has_rate": slot["has_rate"],
            })
        return {"keys": encoded}

    @classmethod
    def from_dict(cls, blob):
        model = cls()
        for slot in blob.get("keys") or []:
            model.keys[(slot["motive"], tuple(slot["activity"]))] = {
                "rate": slot["rate"],
                "sigma": slot["sigma"],
                "has_rate": slot["has_rate"],
            }
        return model


class DurationModel:
    """Last 50 unambiguous completed durations, in game ticks, per affordance."""

    def __init__(self):
        self.samples = {}
        self.seeds = {}

    def observe(self, affordance_id, duration):
        bucket = self.samples.setdefault(affordance_id, [])
        bucket.append(duration)
        if len(bucket) > _DURATION_CAP:
            del bucket[:-_DURATION_CAP]

    def surprise(self, duration, affordance_id):
        bucket = self.samples.get(affordance_id) or []
        if len(bucket) < 3:
            return 0.0
        low = _nearest_rank(bucket, 25)
        high = _nearest_rank(bucket, 75)
        if duration < low / 2.0 or duration > high * 2.0:
            return 3.0
        return 0.0

    def seed_from_calibration(self, report):
        """Remember DA5 medians. Missing keys are skipped. Samples stay empty."""
        if not isinstance(report, dict):
            return self
        for item in report.get("durations") or []:
            if not isinstance(item, dict):
                continue
            affordance = item.get("affordance_id")
            median = item.get("median_ticks")
            if affordance is None or median is None:
                continue
            self.seeds[affordance] = median
        return self

    def reset(self):
        self.samples = {}

    def to_dict(self):
        return {
            "samples": {str(key): list(value) for key, value in self.samples.items()},
            "seeds": {str(key): value for key, value in self.seeds.items()},
        }

    @classmethod
    def from_dict(cls, blob):
        model = cls()
        for key, value in (blob.get("samples") or {}).items():
            model.samples[_coerce_id(key)] = list(value)
        for key, value in (blob.get("seeds") or {}).items():
            model.seeds[_coerce_id(key)] = value
        return model


def _coerce_id(key):
    if isinstance(key, str) and key.lstrip("-").isdigit():
        return int(key)
    return key
