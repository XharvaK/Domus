# Amendment A15

| A15 | §5 interaction tuning dump (schema unchanged, still v4) | Probe 2.4.0: inbox command `atlas_dump` writes whitelisted interaction tuning fields to `atlas/tuning_<sims_build>.jsonl` in budgeted chunks. The presence snapshot row is unchanged. `commodity_flags` and `target_type` are omitted (not pure). | DO-1: `services.tuning_managers` is a module global; `all_instances_loaded` is a getter that only reads `_load_all_complete`; `_tuned_classes` is a plain instance attribute. |
