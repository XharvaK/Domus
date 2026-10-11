"""The percept vocabulary and the decision log's quota. The tuned numbers of the old thalamus are gone (D2)."""

# Owner-adjustable. Decision JSONL under data_dir/thalamus is kept until this many bytes.
DECISION_LOG_QUOTA_BYTES = 50 * 1024 * 1024

KINDS = (
    "need", "interaction", "posture", "presence", "social",
    "moodlet", "env", "lineage", "gap", "look",
)
