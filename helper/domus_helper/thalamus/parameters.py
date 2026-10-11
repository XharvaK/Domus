"""The percept vocabulary and the decision log's quota. The tuned numbers of the old thalamus are gone (D2)."""

# Owner-adjustable. Decision JSONL under data_dir/thalamus is kept until this many bytes.
DECISION_LOG_QUOTA_BYTES = 50 * 1024 * 1024

KINDS = (
    "need", "interaction", "posture", "presence", "social",
    "moodlet", "env", "lineage", "gap", "look",
    # 2.36.0 (D6): a notice the game showed her (title and text), and a change to her own self (one thing).
    "notice", "self",
    # 2.37.0 (W10 H2): her choices (options) were left out of a view the contract refused; the why is in facts.
    "options_dropped",
)
