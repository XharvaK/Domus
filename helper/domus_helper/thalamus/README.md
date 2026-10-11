# Thalamus package (what it is now)

This package turns game telemetry into what Ashley sees. It no longer decides anything (D2).

- `percepts.py`: the Extractor. `Extractor.step(row)` reads one row and returns percepts: facts about the body and the
  world (a need's band changed, an interaction started or ended, a posture, a room, a presence, a question the game
  opened). It keeps the small state it needs between rows (`to_dict` / `from_dict`).
- `observation.py`: the view builder. `build(decision, ctx)` turns the percepts it is given (`decision.percepts` as
  `(percept, salience)` pairs) and the body row into one observation. The bridge always passes salience 0.0.
  `SeenMemory` keeps who she sees, by a keyed handle.
- `types.py`: `Percept`, the one value the package passes around, and its plain-data form.
- `parameters.py`: the percept kinds and the decision log's quota.
- `log.py`: the append-only log of views sent (one line per view: time, trigger, percept count, kinds, observation id).

What sends a view is `domus_helper/coalesce.py`, which the bridge calls: pending changes go out once nothing new has
come for 1.5 s, or the oldest pending change is 8 s old, or a question the game opened for her is pending (at once).
The tuned numbers of the old thalamus (arousal, habituation, novelty, threshold, refractory, boredom, the slow check)
were removed; so were its scorer slot and its replay tool.

Central fixtures in `vectors/central/` are vendored byte for byte from Ashley and are checked for their bytes only.
