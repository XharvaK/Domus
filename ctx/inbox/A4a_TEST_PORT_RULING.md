# A4a: Ruling on the A4 STOP (porting the C4 outcome tests). Resume A4.

From: Architect, 2026-10-01. To: the A4 implementer. **This ruling resolves the conflict and amends A4 Build items 2–3.** Every other part of A4 stands as written.

## What the legacy code actually does (verified)

- `core/cognitive-graduation/outcome.test.ts:20–51`: **recording an observation never adjudicates.** `recordCognitiveOutcomeObservation` writes the observation and moves the prediction to `observation_available`, and `listCognitiveOutcomeAdjudications` is still `[]`. A `receipt_backed` observation also **requires `observedValueTyped`** (`cognitive_graduation_observed_value_required`).
- `outcome.test.ts:87–140`: adjudication is a **separate, explicit call**, `recordCognitiveOutcomeAdjudication(..., adjudicationAuthority: "deterministic_compare")`, accepted only for typed comparable values. Adjudications are append-only (`supersedesAdjudicationId`; an UPDATE throws `cognitive_adjudication_append_only`).

## The ruling: two layers, with no change in meaning

1. **The observation layer keeps C4's semantics exactly.** `recordObservation` (ported) never adjudicates. Port the legacy tests at this layer **unchanged in meaning**, including "does not adjudicate on receipt", the typed-value requirement, missing/`outcome_unknown` with no adjudication, and append-only.
2. **The adjudication API keeps C4's general rule.** `deterministic_compare` is allowed only for typed comparable values. Port that test as is. The API is general; it's a library rule, not a recorder.
3. **A4's "exactly two comparators" limits the Host recorders,** the automatic choke points, not the API. Each of the two recorders does **two explicit calls in one transaction**:
   - `recordObservation(...)` with a typed value and the receipt reference, and **no message text**:
     - `owner_reply`: `observedValueTyped = {replied: true}`, with the receipt type `owner_message` and the receipt ID set to the admitted message ID;
     - `delivered`: `observedValueTyped = {delivered: true}`, with the receipt type `delivery_receipt` and the receipt ID set to the receipt ID;
     - at the horizon with nothing found, `observationKind = "missing"` and no value;
   - **then** `recordAdjudication(... "deterministic_compare" ...)`: `receipt_backed` with a matching value becomes `confirmed`, and `missing` becomes `contradicted`.

   No other code path adjudicates automatically.
4. **New tests** (red-first) for each of the two recorders:
   - observation plus adjudication in one transaction;
   - idempotent per `(expectation_id, kind)`;
   - a throwing recorder doesn't alter the delivery or admission path;
   - no message text in any row.

   They sit **alongside** the ported legacy tests and don't replace them.
5. **In the report,** list each legacy test as **ported unchanged** (observation and adjudication layers) or **dropped, with its reason** (e.g., a test that needed nuclear-only fixtures with no sidecar equivalent). Don't change what any ported test asserts.

## Resume

Continue A4 from its current state, with this ruling in the brief's STATE block. **The other STOP conditions in A4 still apply.**
