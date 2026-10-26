STATUS: DONE

Snapshot only (live file was still growing): 1800 rows, probe 2.7.0, session `c964da78-8841-41c4-ab87-3895fb228b2d`, presence 1736, social entries 0, presence entries 0. Copied beside this report's sibling `raut/`. Labels: VERIFIED from that snapshot, INFERRED, UNKNOWN, WEB.

Rerun (stdout is the full number dump; `proposed_need_cards.json` is rewritten):

```powershell
& "C:\Users\Xharv\Projects\Domus\helper\.venv\Scripts\python.exe" "C:\Users\Xharv\Projects\Ashley\_Internal\work\raut\analyze.py" --session "C:\Users\Xharv\Projects\Ashley\_Internal\work\raut\session_snapshot.jsonl" --decisions "C:\Users\Xharv\Projects\Ashley\_Internal\work\raut\decisions_snapshot.jsonl" --atlas "C:\Users\Xharv\AppData\Local\Domus\atlas.db" --tuned "C:\Users\Xharv\Projects\Domus\sims-e1\evidence\TUNED_RECHECK_2_6_0_2026-10-04\tuned_1.128.90.1030_1791063960516.jsonl" --cards "C:\Users\Xharv\Projects\Ashley\_Internal\work\raut\proposed_need_cards.json"
```

`ashley_e1/__init__.py` pulls the game, so the script loads `e2_cards.py` through a stub package. It calls `calibration.analyze` (coverage: affordances 95, autonomy spans 240, gaps 2; ticks NORMAL 426720, SPEED3 8772675, SUPER_SPEED3 4789363).

## 1. What autonomy did — VERIFIED

240 closed autonomy RUNNING spans (includes `QUEUED_AND_RUNNING`), 0 ambiguous, 0 left open. Another autonomy SI was already running on the end row in 39/240 (completion handoff). 0 of those were under 60 sim-seconds. 4 spans were under 60 sim-seconds and ended with no SI. Separate cancel channel: BODY_CANCEL_AOP 95 interaction ids, CARRY_CANCEL_AOP 37. Object catalog names are not in the log; targets are instance ids.

| n | med sim-min (IQR) | med ticks (IQR) | lowest actionable at start | name | pre medians H/E/B/Hy/F/S |
|---|---|---|---|---|---|
| 37 | 9.53 (9.45–9.63) | 14287 (14168–14439) | hunger 13, energy 11, hygiene 11 | Bed_Undercovers_Cry | 62/69/68/77/100/0 |
| 27 | 14.35 (14.13–14.61) | 21518 (21189–21918) | energy 14, hygiene 6, hunger 6 | book_read | 58/60/72/85/99/0 |
| 25 | 57.15 (42.31–85.20) | 85729 (63462–127799) | energy 8, hygiene 7, hunger 6 | tv_WatchNews | 69/67/70/75/99/0 |
| 23 | 9.64 (9.03–14.01) | 14462 (13544–21021) | energy 9, hygiene 7, bladder 4 | book_read_browse | 62/65/73/86/99/0 |
| 13 | 14.29 (9.53–14.85) | 21427 (14287–22270) | hunger 11 | generic_consume_food | 31/81/70/58/97/0 |
| 12 | 4.77 (4.66–4.82) | 7161 (6993–7231) | hygiene 6, energy 5 | sink_washDish_After_Eat_Counter | 85/79/68/58/95/0 |
| 11 | 4.75 (4.67–4.79) | 7126 (7000–7182) | hunger 8 | sink_washHands | 62/81/100/68/98/0 |
| 10 | 9.34 (4.73–9.50) | 14007 (7091–14252) | bladder 10 | toilet-use-sitting | 37/74/17/61/98/0 |
| 9 | 14.16 (13.92–14.36) | 21238 (20874–21532) | bladder 3, hygiene 3 | phone_BrowseWebsites_AutonomousOnly | 64/56/49/82/99/1 |
| 7 | 420.3 (376.6–524.6) | 630433 (564917–786844) | energy 7 | bed_sleep | 61/36/54/71/99/0 |
| 4 | 31.27 (23.91–47.85) | 46909 (35868–71776) | hygiene 4 | shower_TakeShower | 65/91/58/4/81/4 |

Social was in the lowest-motive tie on 228/240 starts. No action cleared a +social card, so a match against that full lowest set is 4/127. Against the lowest of the other five: 34/119 spans whose affordance has a +card (28.6%, INFERRED, same-session effects) and 44/174 by name lexicon (25.3%, INFERRED). Toilet, shower, sleep, and food do track bladder, hygiene, energy, and hunger. The mass of starts is cry, read, and TV while fun is already ~99–100.

When no hunger/energy/bladder/hygiene/fun band was low or distress: 513 rows, and 394 of them still had a non-posture SI. Postures then: sit 293, stand 144, shower 37, bed_Undercovers 36. Rows with no such SI: stand 105, sit 8, bed_Undercovers 6. Overall postures: stand 728, sit 642, bed_Sleep 132, bed_Undercovers 111, shower 73, toilet_sit 33, cook 8, bed_Nap 5, showerClean 4.

## 2. Effect table — VERIFIED arithmetic, control is biased for hunger

Per game-hour = sum of motive delta / sum of sim-hours while that affordance is the only non-posture RUNNING SI. Control = no such SI: 40.017 sim-hours, 605 intervals. Control rates /game-hour: bladder −2.049, energy −3.673, fun −3.324, hunger **+4.723**, hygiene −0.700, social −0.825. Hunger idling upward is the meal credit landing after `generic_consume_food` ends (INFERRED). Decay prior from long non-food bouts is hunger about −4.4 (sleep) to −6.1 (TV news) per game-hour.

| affordance | hours | motive rate (excess vs control) |
|---|---|---|
| bed_sleep | 51.31 | energy +8.56 (+12.23); hunger −4.37 (−9.09) |
| tv_WatchNews | 25.16 | hunger −6.12 (−10.84); fun stayed near cap, no +fun card |
| book_read | 6.61 | fun +8.02 (+11.35); hunger −5.75 (−10.48) |
| Bed_Undercovers_Cry | 6.08 | hunger −10.21 (−14.93); bladder −7.90 (−5.85); no motive goes up |
| book_read_browse | 3.77 | fun +11.14 (+14.47) |
| generic_consume_food | 3.13 | hunger +124.93 (+120.21) |
| shower_TakeShower | 2.52 | hygiene +121.25 (+121.95) |
| tv-watch-sports | 2.57 | fun +22.96 (+26.29) |
| toilet-use-sitting | 1.38 | bladder +448.06 (+450.11); hygiene −39.02 (−38.33) |
| sink_washHands | 0.87 | hygiene +71.61 (+72.31) |
| phone browse | 1.19 | fun +2.51 (+5.84) |

`raut/proposed_need_cards.json`: 29 cards, each `validate_card`'d, `min_net_delta` 5.0, `object_id` null. Bar: |excess| ≥ 5 /game-hour, ≥ 0.25 sim-hours, ≥ 4 intervals, span n ≥ 2. The +direction cards are the useful proposals (sleep/energy, shower/hygiene, toilet/bladder, food/hunger, wash-hands/hygiene, read/sports/phone/fun). The −hunger cards on almost every long action repeat the contaminated control. Fun on dish-washing (+29.4, 1.04 h) is a weak co-occurrence. Not written to the atlas.

## 3. Coverage — VERIFIED

Tuned file: 321 rows, 577 unique guids, 212 `allow_autonomous`, 577 `is_super`, 3 `is_social`. Autonomy ran 41 guids; 26 are in the 577 and 15 are not. Of the 41, 15 have `allow_autonomous` false, including `bed_sleep` 13094, `bed_Nap` 13091, `tv_WatchNews` 9111, `tv-watch-sports` 14489, `book_read` 13117, and `book_read_browse` 76988. Of the 212 autonomous-allowed lot guids, 20 ran and 192 never did (191 other + 1 social in the partition below).

Never-used 551, partition: not autonomous-allowed 359, social 1, other autonomous-allowed 191. Overlap counts (not a partition): picker in the name 61, debug/cheat/testing in the name 68, `is_social` 3. `require_current_posture` is only 23 rows in the whole atlas. `posture_preferences` is `ImmutableSlots` on all 8256 rows, so it does not mean posture-only.

Atlas build `1.128.90.1030`, 8256 rows: autonomous-allowed 4239 (autonomous-only 1874, both flags 2365), not allowed 4017 (user-directed-only 3338, neither flag 679), social 1465, not social 6791, super 6033.

Autonomy cannot show user-directed-only interactions, the 1465 social affordances (this lot offered 3), picker/debug tunings, skills, career, or off-lot life. It also ran some `allow_autonomous=0` supers, so that flag is an incomplete mask (INFERRED: continuations).

## 4. Motive dynamics — VERIFIED

25 ticks = 1 sim-second at every speed, so `NEED_FRESH_TICKS` 2000 = 80 sim-seconds. Median `age_ticks` 5399 (216 sim-seconds); p90 20042; max 166184; fraction over 2000 = 0.7551. Median age on a row where the value changed = 2085, just over the gate. The gate would reject most samples, including the typical update. No motive was flat (range ≥ 1). Social 0 on 868/1736 rows, max 45, never band `ok` (distress 133.25 h, low 22.18 h).

| motive | idle /game-h | first low | first distress | hours ok / low / distress | min–max |
|---|---|---|---|---|---|
| bladder | −2.05 | 71.4 min | 502 min | 98.9 / 50.1 / 6.5 | 10–100 |
| energy | −3.67 | 4.8 min | never | 109.1 / 46.3 / 0 | 26–100 |
| fun | −3.32 | 7740 min | never | 155.2 / 0.24 / 0 | 50–100 |
| hunger | +4.72 (see §2) | 306 min | never | 83.6 / 71.9 / 0 | 22–100 |
| hygiene | −0.70 | 1547 min | 4766 min | 111.0 / 37.3 / 7.1 | 4–100 |
| social | −0.83 | 6662 min | 4.8 min | 0 / 22.2 / 133.3 | 0–45 |

Sleep, autonomy `bed_sleep`, energy before→after and sim-min: 36→100 in 420; 26→100 in 445; 36→100 in 413; 37→100 in 525; 35→97 in 377; 26→86 in 363; 37→100 in 536. Nap 37→52 in 114. Each night started in `SUPER_SPEED3`.

## 5. Speed and time — VERIFIED

Sim clock 23:11:01.960 day:1 week:0 → 10:41:38.440 day:1 week:1, 7 midnights, 155.51 sim-hours (9330.61 sim-min). Ticks 4246549 → 18242461. Unpaused wall 29.548 min. Presence speeds: SPEED3 1212, NORMAL 390, SUPER_SPEED3 134.

| speed | ticks / wall-s | sim-s / wall-s | pairs |
|---|---|---|---|
| NORMAL | 1071.262 | 42.850 | 390 |
| SPEED3 | 7086.871 | 283.475 | 1210 |
| SUPER_SPEED3 | 35037.368 | 1401.495 | 134 |

8 drops, all `SUPER_SPEED3`→`NORMAL`, none `SPEED3`→`NORMAL`. Each drop's left row was still `bed_sleep`+`generic_Bed_Sleep` (or `bed_Nap` at seq 1675) with energy already high: seq 50, 334, 811, 1031, 1251, 1490, 1675, 1756. That is the post-sleep return the Owner saw. Commands in the log: arm 1, calibrate 1, start 1, status 4. Experiment phases: CALIBRATE_START 1, CALIBRATE_SPEED 24.

## 6. Thalamus — VERIFIED counts; theta curve UNKNOWN

Decision file: 790 rows, 0 below `wall_ms` 1791105000000 (this copy has no earlier dry-run prefix). Theta logged 1.0 on all 790. Inside the telemetry wall window: 74 fires / 29.548 min = **2.5044 /min** (threshold 65, always_through 9). Band 0.20–0.33 is about 8–12× lower. Always-through alone is 9/29.548 = 0.305/min.

`salience_sum >= theta` agreed with `fired` on 529 rows, disagreed on 197, 64 rows had no traces. Top salience sums: `interaction:…:13983:ended` 62.91 (sim-stand), `need:fun::ok` 27.76, `need:hunger::ok` 23.87, `need:hunger::low` 21.77, `interaction:…:31564:ended` 20.13. Families: interaction 306.03, need 180.18, posture 49.28, lineage 4.4, gap 2.2. One trace key cites the DT2b fixture id `b4ad0449`, one cites this live session.

A theta0 curve is not honest from these traces. Fire is accumulated arousal, then a debounce, plus refractory, boredom, and always-through; `raw >= theta` also changes other keys' habituation, and urgency/pressure are not logged. Row fractions with post-decision arousal ≥ t, which are not fire rates: 1.00→0.798, 1.25→0.763, 1.50→0.733, 1.75→0.708, 2.00→0.667, 2.25→0.635, 2.50→0.600, 2.75→0.568, 3.00→0.553. Median arousal 3.47. Naive salience-sum ≥ t fractions: 1.00→0.260, 1.50→0.102, 2.00→0.058, 2.50→0.032, 3.00→0.011.

## 7. Gaps, ranked by how hard they block Ashley's own choices

1. The log is the winner, not the scored candidate list. DA6 and E3 need advertisements, static commodities, and `test_autonomous`. NEEDS_SOURCE (decompiled scripts are not on this machine). WEB only: false advertisements add or subtract an autonomy score from motive stats, and static commodities are fake desires that bias the pick ([Sims 4 Studio, TV autonomy](https://sims4studio.com/thread/25008/decreasing-autonomy-on-object); [Zero, static commodities](https://www.patreon.com/zer0_Mods_/posts/tutorial-static-45387750)). Mood and trait weights sit in the same score ([social content-score thread](https://sims4studio.com/thread/11453/social-tuning-content-score-weighting); [trait-autonomy commodities](https://sims4studio.com/thread/37743/help-explaining-commodity-trait-autonomy); [interaction content score](https://www.patreon.com/posts/tutorial-lets-31955640)). `allow_autonomous` / `test_autonomous` are the gates ([modding wiki](https://sims-4-modding.fandom.com/wiki/Interaction); [test_autonomous injection](https://triplis.github.io/nav/guides.html)).
2. Social life. Presence and social arrays are empty, yet `sim_Chat` (3) and `sim_BeAffectionate` (4) ran at instance ids `11824504378950xxxx` while social was usually 0. UNKNOWN what those targets are. Cheapest LAB: one invited Sim, autonomy on, aging off, speed 3, and check that presence/social stop being empty.
3. Need-card math is censored: fun sits at 50–100 so TV news shows no fun gain; hunger credit misses the eat span; 75.5% of ages fail 2000 ticks. Cheapest: keep this session, retune the freshness gate, attribute the meal to the eat span plus the following idle minute. A second LAB is not required for that.
4. Mood and moodlet names. Mood type is a bare id (14643 on 1079 rows); `game_text` is null on every signal. Cry ×37 with fun at 100 is unreadable until those ids are named. WEB/source lookup, not a new lot.
5. Skills, career clock, off-lot, money. Absent from the schema. LAB later: one skill object; then a job; then leave the lot. Lower urgency than 1–4 for in-lot need choices.
6. `allow_autonomous=0` still ran for sleep, reading, and TV news. NEEDS_SOURCE (continuations vs the flag).

## 8. How much to trust it

Use it for duration priors (sleep ~6–9 sim-hours, IQR tight; toilet ~9 sim-min; shower ~31; many chores locked near 4.7 or 9.5 or 14.3 sim-min) and for effect priors where the swing is huge (toilet/bladder, shower/hygiene, food/hunger, sleep/energy, wash-hands/hygiene).

Do not use it as what Ashley should do. Social was the worst motive on 95% of starts and stayed unsolved. Fun was maintained at the cap (read seq 5-class, TV news 25 spans, phone 9). Cry ran 37 times from comfortable motives (example seq 1050, hygiene 7, fun 100, hunger 84). Distress emotes preceded the remedy: bladder-distress seq 294 (bladder 14) and 1464; hygiene-distress seq 1038 (hygiene 12) then sink-clean seq 1040 and reading seq 1053 while hygiene was 6. About three quarters of non-social starts did not serve the lowest actionable motive.

## Top 5 next steps

1. Re-run the command above on the finished jsonl when the Owner stops the session.
2. Keep the six +direction priors; do not load the 29 cards into the atlas; drop −hunger cards until meal credit is aligned with the eat span.
3. One social LAB (one visitor). Confirm whether chat targets were objects.
4. Leave theta0 at 1.0 until a real replay exists. 2.50 fires/min is mostly `threshold`; always-through alone is already 0.305/min, inside 0.20–0.33. The missing fields are urgency, pressure, and theta-dependent habituation.
5. Source pass on the autonomy score and on why `allow_autonomous=0` supers still run. Name mood ids 14643, 14646, 14640, 27149 before anyone interprets the cry loop.
