"""dt2.v1 numeric contract. Every tuned number lives here."""

from dataclasses import dataclass, field

PARAMETER_REVISION = "dt2.v1"

# Owner-adjustable. Decision JSONL under data_dir/thalamus is kept until this many bytes.
DECISION_LOG_QUOTA_BYTES = 50 * 1024 * 1024

KINDS = (
    "need", "interaction", "posture", "presence", "social",
    "moodlet", "env", "lineage", "gap",
)

bounds = {
    "theta0": (0.5, 3.0),
    "alpha_ambient": (0.3, 0.8),
    "alpha_social": (0.0, 0.8),
    "alpha_always_through": (0.0, 0.0),
    "recovery_tau_ms": (600_000, 600_000),
    "arousal_tau_ms": (60_000, 60_000),
    "refractory_ms": (20_000, 20_000),
    "debounce_ms": (1_500, 1_500),
    "novelty_beta": (0.6, 0.6),
    "dishabituation_fraction": (0.0, 1.0),
    "arousal_reset_fraction": (0.0, 1.0),
    "surprise_cap": (3.0, 3.0),
    "wake_boost": (0.0, 1.0),
    "action_end_boost": (0.0, 1.0),
    "boredom_rise_ms": (900_000, 900_000),
    "resting_rise_multiplier": (2.0, 2.0),
    "w_kind": (0.25, 4.0),
}


def _weights():
    return {kind: 1.0 for kind in KINDS}


@dataclass(frozen=True)
class Parameters:
    theta0: float = 1.0
    alpha_ambient: float = 0.3
    alpha_social: float = 0.1
    alpha_always_through: float = 0.0
    recovery_tau_ms: int = 600_000
    arousal_tau_ms: int = 60_000
    refractory_ms: int = 20_000
    debounce_ms: int = 1_500
    novelty_beta: float = 0.6
    dishabituation_fraction: float = 0.5
    arousal_reset_fraction: float = 0.0
    surprise_cap: float = 3.0
    wake_boost: float = 0.5
    action_end_boost: float = 0.5
    boredom_rise_ms: int = 900_000
    resting_rise_multiplier: float = 2.0
    w_kind: dict = field(default_factory=_weights)


def validate(params):
    for name, (lo, hi) in bounds.items():
        if name == "w_kind":
            weights = params.w_kind
            if set(weights) != set(KINDS):
                raise ValueError("w_kind must set every percept kind")
            for kind, value in weights.items():
                if not lo <= value <= hi:
                    raise ValueError(f"w_kind[{kind}] {value} outside [{lo}, {hi}]")
            continue
        value = getattr(params, name)
        if not lo <= value <= hi:
            raise ValueError(f"{name} {value} outside [{lo}, {hi}]")
    return params
