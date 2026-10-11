# Ashley Sims 4 Embodiment probe

This directory contains the owner-commanded Sims 4 Embodiment probe.

## Current build: 2.35.0 (going places on the lot: spots and Go Here, the phone's refusals read)

2.35.0 (D3): observation schema 17. Spots: her menu lists a standable spot per room and level that has objects on her lot, and the front door outside (when the game has one). A spot is an object of the menu with the class `spot`, `spot` (`room` or `front_door`) and `level`; the game's own standable search finds where she would stand near the room's object nearest its centre, and the spot is listed only in the room it was asked for. Its act is the game's Go Here (`terrain-gohere`), tested like any other act: the target is the game's TerrainPoint at the spot, the context carries the game's pick (PICK_TERRAIN, or PICK_POOL_SURFACE in a pool), and the same preflight, push and receipts follow. An act on a spot id the newest finished menu build does not hold, or one from another zone, is NO_OBJECT. Spot ids are small (1 to 999) and kept for the session per room, level and kind. The phone's refusals (D4a, a diagnostic only): the game's preflight test refuses some of her phone's offers, and part 0 of the menu names each one by its tuning name and reason key (`refused_phone`, at most 16; `reason_key` is null when the tooltip has none). The menu itself does not change with it.

## Previous build: 2.34.0 (her whole lot in her menu, identical acts once per object, the game's own windows hers)

2.34.0 (N8, after the first live play): her act menu covers every object on the lot that offers her something, not the
nearest 30; each object carries its room. The menu is written in parts of 16 objects (one record each, same
`menu_rev`), and the helper shows it once all its parts are in. A window or a client screen that the game opens while
her act is being pushed is hers (held for her, or withheld), not the User's. Schema 16: the object's `room` and the
menu's `part` and `parts` are new; the observation schema is 16 and the helper accepts rows of schema 4 to 16.

2.33.0 reads the inbox oldest command first, by when it was issued, not by its random file name (at most 64 files
are looked at, then four are read per tick). An act that is past its time is refused as an act: an `act_event`
REJECTED with code EXPIRED for its id, so Ashley hears it, as well as the command reply.

The source is version `2.35.0` (`src/ashley_e1/__init__.py`,
`src/ashley_e1/schema.py`; observation schema 17; the helper's vendored copy follows it). It is no longer read-only:
it carries the E2 actuation experiment described by
`docs/Domus/PROJECT_ASHLEY_SIMS4_EMBODIMENT_E2_IMPLEMENTATION_READY_PLAN_V1.md`.
The file the game lists is `Domus_<version>.ts4script`. The package inside stays `ashley_e1`.
2.34.0 has not yet passed its E2 first-load gate or trials; those run on the
Owner's Windows dev PC. `calibrate` while armed refuses actuation and only observes.
Class cards judge a trial by posture, need, interaction, or social purpose.
`trial` pushes one parameter-free super-affordance on the lab fork and judges it
with an interaction card. Sit and sit_trial are unchanged. After the verdict the probe
cancels only the interaction it pushed for that trial, so the next trial finds an idle body (A25).

2.32.0 (schema 15, W5d) adds to the observation row. `presence` carries `is_pet`, `species` and `occult_kinds`
(each None when unreadable). `self.life` carries the age stage, `pregnant`, `sick`, `dead`, `ghost` and `npc`.
`body.is_selected` says whether the Sim the client plays is her body; while it is not, her acts are refused with
BODY_MISMATCH (NOT_ACTIVE). `game` carries `build_mode` and `fire`; a refusal during a fire or in build mode is
named FIRE_REFUSED or BUILD_MODE_REFUSED. `objects` carries `near_conditions` (the notable states of the 16 nearest),
`near_rooms`, `moved` (from and to room) and `owner_changed` (from and to household). A death writes one
`lineage_event` with record BODY_GONE and a `reason` (DEAD or GHOST), then sampling stops. A `dropped_summary` carries
`drop_detail` (the row kind and the field that failed). The camera takes an `unfollow` op (look at her, not follow).
Seen Sims: a Sim is seen within her room and level (outdoors, within 4 m on her level); the helper names only those.
Not yet read: the game build (PR14 stays a constant), the owner of objects beyond the 16 nearest, a fire's distance.

2.32.0 takes over every window her act or her game opens. A dialog or a phone call she can answer is held for
her; the User sees it only after 180 s unanswered, and a late answer is then refused. A window she cannot answer
(colour, composite, map, apartment) is shown to the User at once. A window that renames her Sim or changes its traits
is always the User's. A client screen her act opens (the event planner, the family tree, the bills panel) is
withheld and her act records it. Other people's windows are untouched.
Her dialog report (schema 14) says whether she holds each window, who it belongs to, how many rows she may pick, the
purchase counts, and for a held text window each field's length and value limits. Her answer may pick several rows,
counted purchase rows, or text for every field; the probe checks each against the held message and refuses with a
code, and never logs her text.
The helper sends her pace with `pace` (`need_drain` and `slow_time`, fractions of normal pace where 1.0 is off; nothing
applies until it does). Her motives drain at `need_drain` through the game's own decay-rate modifier while she is
sampling, and the modifier comes off at stop; `slow_time` slows the game clock the same way, only when the clock is at
the game's defaults. Each observation's `pace` block says what the probe applied.

## Crawl (DA6)

`preflight` (LAB only, not during calibrate) asks the game which tuned offers it would refuse and writes `preflight_<build>_<ms>.jsonl` beside the tuned scan. The crawl plans only rows that preflight marked ok when that file is newer than the tuned scan. The crawl runs a fresh preflight at start and waits while it grows (`--no-preflight` reuses the newest one instead of running another). Game refusals are `PUSH_REFUSED` and are not push failures. A missing object is `STALE_TARGET` and stays plannable on another object; three of those in one run repeat the tuned scan and the preflight. A push that never runs is `NEVER_STARTED`. A displacement before attribution is `INTERRUPTED`. Natural finishes and script-children of our own push can pass. At the start the crawl prints one environment line naming objects whose every tested affordance was refused for the same reason, so a burnt or broken object can be repaired before trials. Outcome lines carry `needs_before` and `needs_after`. `OUTCOME_UNKNOWN` rows from probes before 2.10.0 stay in the ledger and do not count toward qualification.

## Food (DA6D)

Two pushes never open a dialog when the source is the probe's script source. `auto_craft` is `StartCraftingAutonomouslySuperInteraction` (snack guid 13397, cook guid 13388): the game picks a weighted recipe and crafts, after a funds check. `StartCraftingOrderAutonomouslySuperInteraction` is not that route. `auto_pick` is `AutonomousObjectPickerInteraction`, or an `ObjectPickerInteraction` whose name contains leftover or snack: the game picks an existing item and pushes the continuation. The trial is still `push_affordance`. No choice callback and no dialog.

Every other picker stays excluded, including the user-directed fridge pickers (77672, 13387, 76891–76905, 75761, 156400–156404) and ordering, catering, and purchase pickers. `Interaction.test` does not read `allow_user_directed`, so exclusion is the class route, not that tuning flag. Social and deny-name checks still apply to a food route.

`food_scan` (LAB, not during calibrate) writes `food_<build>_<ms>.jsonl` and reads each crafting menu with `picker_rows_gen` and no instance, which does not reserve ingredients. `python -m domus_helper.food --eat` pushes one route, preferring an auto-pick leftover or snack, then snack 13397, then cook 13388, and skips a route preflight refused. The crawl never plans 13388 or 13397. The card is hunger, direction +1, judged over the whole family (the push hands off to the game's own phases), with a 600 s ceiling. It closes once the effect has held 10 s, or 30 s after the family was last live. A running food family is never cancelled; a push that is still only queued is cancelled.

On the first live run, watch household funds, a platter left out, whether the stove is used, and a fire.

## Live hardening (DA6E)

The first real-needs session (2.11.0, no fill cheat) showed each of these. With a body need in distress the trial guard still admits a cure for it: food for hunger, sleep or a nap for energy, the toilet for bladder, a shower or bath for hygiene. Cleaning or upgrading the same object is never a cure. A trial pushed while a need it relieves is low is a relief trial: its running action is never cut at the verdict. A stale motive reading is no reading for that row, not an ambiguity for the trial.

The crawl asks for a fresh preflight when it starts. After a relief trial it waits for her to finish and logs `needs_finish`. `crawl --relief-survey` is an opt-in lab mode: when a body need is at or under 35 it measures that need's cure before the next trial. That is telemetry for the references Ashley reads. It is not her policy; what she does is her own decision.

## Live hardening (DA6F)

The second session (2.11.1) added these. A motive's `value` is the game's current value: the probe applies the game's own rate formula to the cached value without writing it, so a reading is current at any game speed (`age_ticks` 0). Only if a rate cannot be read does it report the cache and its age. Sleep and work switch the game to speed 3, where rows are about 37000 ticks apart. A maintained interaction trial ends 30 s after it finishes, not at its 180 s window, and a relief trial's verdict carries the need's start, peak, and end (`relief=energy energy=24->100->100`). The crawl does not push a trial into a body distress it can already see, and its stop names the need. Preflight and the food scan tick four times a second at the same 5 ms budget and show progress on `status`. The food scan matches name words, not substrings ("eat" no longer matches cheat or death), reads menus only from classes that have one, and names recipes. `remove.ps1` without `-Version` removes every installed probe package.

## Ashley acts (2.16.0, schema 10)

Two new row kinds. `act_menu` is what she can do near her body: while sampling, every 20 s or when her room changes, the probe lists the objects of the lot she is on, her room first, then the rest of the lot, then what is off the lot, nearest first in each (2.18.0). An object that offers nothing never takes a slot; one object per definition; at most 4 from her room, then one object from every other room before any room gets a second (2.18.0; lights, candles and doors last within a room), so choosing a thing in another room is how she moves around the house. The people she can reach (on this lot, or within 15 m) come right after her room, at most 3, nearest first, with their socials toward her: greeting, inviting in, talking (2.18.0); socials that change a life or a household in one click (propose, break up, woohoo, try for baby, move in or out, adopt) stay excluded. A picker act (cook, grab a snack) opens the game's dialog, and the dialog is hers to answer (2.18.0): schema 11 adds each open dialog's rows (option id, name, enabled, price; at most 40, enabled first), and the inbox `answer` command picks a row and presses OK, or presses a button, exactly as the client does (`dialog_pick_result`, then `dialog_respond`); only a dialog that is hers or nobody's, and only an enabled row it offers. Records go up to 32 KiB (was 16) so the rows fit. For each, the user-directed affordances the trial guard does not exclude (no pickers except dialog-free food routes, no socials, no deny names) and the game does not flag as cheat, debug or automation, and asks the game, a few at a time within 8 ms per sampling tick, whether it would refuse each one now (`test_super_affordance`, no push). At most 24 objects with 8 acts each (2.19.0, was 12: a nine-room house left the kitchen and the bedroom out); an object offering exactly the acts of one already listed is the same choice and is skipped (people never are). A row is written only when the menu changed. Records go up to 48 KiB (2.19.0). Schema 12 adds her jobs to `self.careers` (career, name and title keys, level, at work), and a work event's buttons, which the game builds as small functions, carry the text key read from the function's closure. 2.19.1: a pie-menu picker (its choices are pie entries the client sends back, so a push carries none) is not on her menu; a pushed act missing from her queue for 5 samples in a row with no finish from the game is recorded UNKNOWN with code LEFT_QUEUE. 2.20.0: the inbox `cancel` command stops one of her own actions, running or queued, exactly as the client's X on her queue does (`find_interaction_by_id`, else `find_continuation_by_id`, then `cancel_user`); the game may refuse (GAME_REFUSED), and a stop is recorded FINISHED with finishing type STOPPED. 2.20.1: right after an answer the probe sends the game's queued client events at once (`Distributor.process_events`, which is what the game's own `add_event(immediate=True)` does), so the close the game queued for the client's dialog does not wait for a later distributor pass; `distributor.system` may be imported for `Distributor` only, and a failed send never changes the answer. 2.21.0: the inbox `camera` command moves only the view (`focus_on_sim` following her Sim, or `focus_on_object` on one object, at most one op each 1.5 s); `camera` may be imported for those two names only, and a look writes no `act_event`. 2.22.0: when the game refuses her act, the refusal tooltip's string key is kept as `reason_key` on the REJECTED act (`PUSH_REFUSED`, and a preflight refusal) and on each preflight row. The read is the tooltip attribute, or the key closed over by a small function, and the tooltip is never called. The helper resolves that key into the game's own sentence; the debug text stays beside it. The key is optional, so observation schema stays 12 and earlier act rows still validate. 2.23.0: after an accepted answer, including cancel, the probe closes the client's window the way the server ends a dialog (`UiDialogCloseRequest`, `MSG_UI_DIALOG_CLOSE`, `add_event` immediate) and lifts only the pause that dialog made (`pop_speed` of `PAUSED` on `UI_MODAL`, else `set_clock_speed` back to the speed recorded on the sample before the dialog appeared). A pause already in place, another dialog still open, or a clock that is not paused is left as it is; a close or resume failure stays on the FINISHED row (`closed`, `resumed`) and never rejects the answer. 2.24.0: the inbox `act` command takes an optional `owner: true`, sent only when her Thought said the User asked for the act; that act is pushed at `Priority.Critical` (every other act stays `High`), so a reflex at `High` queues behind it instead of displacing it, and the ACCEPTED row carries `owner`. A pushed act's FINISHED row carries `started`: true when the game set the interaction's start time (it does so only when the interaction begins), false when it ended before it began (for example the game found no path to it), null when unreadable. Both are optional, so observation schema stays 12. 2.25.0: each menu object carries `reach`: whether the game sees a way from her to it, by the check its own autonomy makes before it picks an object (`ScriptObject.is_connected`, asked once per object per build inside the same 8 ms budget); an object she cannot reach is still listed, with `reach: false`, and `null` means unread. It is optional, so observation schema stays 12 and earlier menu rows still validate. 2.26.0: the inbox `talk` command shows one line of plain text (at most 240 characters, printable) as the game's own notification (`UiDialogNotification`, its default factory with the text as a raw string; owner: the Sim the line is about, when its id is given), at most one line each 2 s, only while sampling her own body; `ui.ui_dialog_notification` may be imported for `UiDialogNotification` only, in `e2_control.py` only. It changes nothing in the world and writes no `act_event`. 2.27.0: a picker that one of her own pushed acts opened (its resolver's interaction or super interaction is that act) is hers to answer, so its window is held back from the User's screen: the probe stands in for `UiDialogObjectPicker.distribute_dialog`, the call that sends the window to the client after the dialog is already open on the server, and keeps the message. The dialog stays open and answerable and is sensed as before; while it is held the client never pauses for it. Her answer drops it (FINISHED `detail: held`); a dialog that closes otherwise is dropped; one still open after 180 s, or at a stop, disarm or re-arm, is sent to the User as the game would have (the User as fallback). `speed_event` records `DIALOG_HELD` and `DIALOG_SHOWN` (code TIMEOUT, STOP or ARM). Every other picker shows as always. `ui.ui_dialog_picker` may be imported for `UiDialogObjectPicker` only, in `e2_control.py` only, and the guard refuses any assignment to a game attribute except that one. A menu failure never stops sampling. 2.28.0: an act follows the interaction the game actually queued. The interaction a push returns, and every interaction the push puts in her queue or running list (compared before and after the push, at most 32 of each), are one act: PUSHED keeps the returned `interaction_id` and lists the others as `aliases` (at most 4; null when there are none, so schema stays 12). A push whose result has no interaction object but that queues one is the same act: its first queued interaction is the `interaction_id`. A push that queues nothing stays PUSH_FAILED. The act counts as present while any of its ids is queued, a picker opened by any of them is held, and its FINISHED row is written once, by whichever finishes first, naming that interaction. 2.29.0: her own phone is one more entry on her menu, right after her room's objects. The game keeps a Sim's phone acts in her own list (`_phone_affordances`, which `potential_phone_interactions` reads), and each candidate is tested the way the others are (`test_super_affordance`, with her own Sim as the target); at most 16 are read, and her phone's entry carries 8 at most. The entry's `object_id` is her Sim's id, with `phone: true` (optional, so observation schema stays 12 and older menu rows validate); it has no distance, room or reach, is never folded with another object, and the helper names it "your phone", so her body is an object she uses and never a person she talks to. An act whose target is her own Sim is offered by her phone's list and by nothing else (`e2_actuator.phone_offers_for`), and the push still targets her own Sim through `push_affordance_ex`, so the 2.28.0 alias tracking applies. Phone acts have their own rule (`e2_actuator.phone_act_excluded`), because the blanket name bans that keep `invite`, `call_`, `phone_call` and socials off objects are exactly what a phone is for: a pie menu stays out, as do names with `PHONE_DENY_PARTS` (testers' acts, money and orders, jobs and business, police, firefighter and burglar calls, life-changing acts, autonomous-only and NPC variants), and any act that would take her off the lot: a class or tuning name, read down its MRO with underscores and spaces ignored, containing `travel`, `goto`, `visitlot`, `mappicker`, `inviteto`, `askon`, `vacation` or `lodging` (leaving the lot changes zones, so those acts need their own design). Pickers (who to call, text or invite over) open a dialog that is hers to answer, held off the User's screen by 2.27.0. 2.30.0: schema 13 adds her wants and fears to `self.wants` (at most 8, fears first): the game keeps them in the Sim's whim tracker (`_whim_tracker`, present only for a fully simulated Sim), one slot each, and the probe reads each filled slot's tuning name, whether its type is `CONFRONTATION` (a fear), and from its goal the name and hint string keys (the tuned `display_name` and `display_tooltip`), whether it is locked, its count so far and how many it needs, and the time of day it expires. All are plain attribute reads: never the goal's `score` (which runs tests), never a tracker method, and nothing is refreshed, locked or completed. A tracker that is absent reads `null`.

`act` (helper inbox only: `act_id`, `object_id`, `guid64`) pushes exactly the action Ashley chose, once per act id. It works in HOME and the lab saves, never during calibrate. It re-checks on the game thread right before the push: sampling, the same body, the object, the offer, not excluded, user-directed, and the game's own test. There is no lab, busy or distress gate: it queues like a player's click, and her body's reflexes still act. `act_event` rows record ACCEPTED (written before the push), then PUSHED with the interaction id and FINISHED with the game's finishing type, or REJECTED with a code, or UNKNOWN when something failed after acceptance. The probe never cancels her action.

## Ashley's home save (2.15.3)

`ashley_e1.arm HOME` arms the probe in Ashley's own save: her household on her lot. It is sensed like the lab saves and its rows validate the same way (schema 9 is unchanged). The lab-only tools check for `LAB_E1` or `LAB_E1_FORK` and refuse there: preflight, the food and situation scans, E2 trials and the helper's actuation. After the User's first `start` in her save, `autosample.json` remembers that save instead of the lab fork, so her save starts sampling by itself on later launches and the lab fork no longer does.

## Launches, place, situations and pop-ups (2.15.2, schema 9)

Sampling carries over to the next launch. When the User starts sampling, the probe writes `autosample.json` beside the telemetry with the save it belongs to. On a later launch, once a zone is running and the loaded save is the same one, the probe arms and starts by itself and writes an `AUTOSTARTED` checkpoint. Another save is never sampled. The User's stop or disarm deletes the file. While the User's start holds, a loading screen with no selectable body is waited out without end; after 60 ticks one `WAITING_FOR_BODY` checkpoint says so.

The telemetry folder holds 1 GiB, and one session may reach it (127 rotations). A `TELEMETRY_DIR_75` checkpoint marks the first row past 75% of the cap, and `status` reports `telemetry_dir` (bytes, cap) and `autosample`. The helper's daily task archives finished sessions and packs week-old archives into weekly zips. Nothing is deleted.

Observation rows carry three new things:
- `place`: whose lot she is on (the zone lot's `zone_owner_household_id`), whether it is her home, and the venue.
- Each presence entry's `situations`: the game situations that Sim is in (a visit, a party), with its role there. They are read from each situation's `_situation_sims`.
- `dialogs`: the game's pop-ups. `open` lists those showing, with kind, owner, title and text string keys, the choices the game offers, and whether the game will answer by itself. `closed` lists those gone since the last row, with the answer the game stored (`ok`, `cancel`, `closed` or a response id). Nothing is answered here.

The size budget trims other Sims' situations, down to the first one each and then none, before it would drop someone addressing her.

## Travel fixes (2.15.1, schema 8)

The game's real-time timers outlive a lot change, so a timer from the last lot can still tick on the next one. At resume the probe cancels it. A tick from any timer that is not the current one only retires that timer and never stops sampling. No rows are written while the zone differs from the one sampling started in, because a lot that is still loading reports her off the lot and without some of her skills.

The inbox tick runs in every zone and watches sampling while the User's start holds:
- It retries a resume that could not start. The first failure writes `guard_exhausted` with `ZONE_RESUME_FAILED`.
- It resumes after a zone change it has not seen yet.
- It restarts a sampler that has not ticked for 10 s, after a `SAMPLER_RESTARTED` checkpoint, at most once every 30 s. A pause of the whole game is not counted as a stall.

The writer flushes rows to disk while sampling is stopped too.

Presence lists her body first, then every Sim on the lot, then the nearest of the rest. When the cap of 8 leaves out a Sim on the lot, the row is incomplete and `missingness.presence` says how many. Sims off the lot that were left out are counted in `missingness.presence_nearby`, and the row stays complete.

Her traits leave out the game's own settings: walk style, hidden traits, tail style, gender options, phone case, locked robot modules and infant carrier.

## Travel, presence and self (2.15.0, schema 8)

Sampling survives travel. Once the User starts sampling, it holds until the User stops or disarms. On a loading screen there is no selectable body; the probe waits up to 60 ticks without writing rows. When the next lot is running it resumes in the same session and writes a `ZONE_RESUMED` checkpoint.

Presence reads each Sim's own instance, so one Sim that is still arriving can no longer empty the list, and her body is always included. Each entry carries `on_lot`, so a friend on the sidewalk is present but off the lot. A Sim that cannot be read is counted: the row is then incomplete, with `missingness.presence`.

Each relationship adds `knows` and `sentiments`:
- `knows` holds what she has learned about that Sim: traits, careers, relationship status, romantic preference and net worth. It is read from her own side of the relationship, never through `get_knowledge`, which creates the record.
- `sentiments` holds her sentiments toward them (Close, Hurt, ...).

Observation rows carry `self`: her traits (personality first), her skills (highest first) and her household money. Skill levels never go through `get_user_value`, which caches a value.

Commodity and statistic trackers are read only from an existing statistic component. The `commodity_tracker` and `statistic_tracker` properties add a component to an object that has none (D42).

## Outcome senses (S5, schema 7)

Each present Sim other than her body carries `relationship`: the friendship, romance and other tracks between them with current values, and the visible labels ("Friends") as string keys, or `known: false` when they have not met. It is read from the relationship service's own records (smaller Sim id first), never through `get_relationship_score`, which can create a relationship. Each moodlet carries `reason_key` (the game's reason, e.g. a spoiled meal) and `minutes_left` for timed moodlets, read from the Sim's commodity tracker without the buff's `commodity` property, which can create one. Observation rows carry `objects`: objects created and destroyed on the lot since the previous sample, and state changes (freshness, dirtiness, ...) of the 16 nearest objects within 4 m. A zone change, the first sample or a pause in sampling starts a new baseline with no events. The size budget trims object events before company, and relationship detail of the farthest Sims next. Situation rows add catalogue tags, who holds the object (`in_use`, `used_by`) and per-minute rates of moving commodities (freshness among them). Time until spoiled stays unknown: the game ties the threshold to state tuning the probe does not read.

## Situation (S1)

`situation_scan` (inbox, LAB only) writes one fact row per object on the lot to `atlas/situation_<build>_<ms>.jsonl`, in 5 ms chunks four times a second: class, definition, position, room, every object state by name (freshness, dish location, dirtiness, ...), statistics and commodities by name with current values (servings among them), and for crafted things the recipe, its display-name string keys and the crafter as the game records it. Plain attribute reads only; no tests and no pushes. The helper's `python -m domus_helper.scene` turns a scan into three layers: near (her room or within 4 m) with full facts and the game's own options, far (one line per object with a notable game state, servings or a recipe), and available (counts by kind). Each layer has a byte budget, order is deterministic, and omissions are counted.

## Senses (DS3, telemetry schema 6)

Each row now says where her body is and who is with her. `zone` carries the zone, lot and room ids and the body's position (`{x, y, z, level}`; the room comes from the game's own `build_buy.get_room_id`, the only name the guard allows from that module). `presence` lists every Sim on the lot, her body first and then nearest first, with name, household, room, position, distance, posture and what that Sim is doing; `social` (who is addressing her) runs whenever someone else is present. Before 2.12.0 presence was always empty: the game yields Sim objects and the reader treated them as SimInfo. Moodlets read their tuned blueprint, so each carries its real name, weight, mood type, visibility and the game's string key for its display name (the helper resolves text from the game's own string tables). Rows may be up to 16 KiB; when one would be larger, hidden and light moodlets go first, then the farthest Sims, and someone addressing her goes last. A session may rotate 127 times (2.15.2). The helper's observation portrait adds the game time (weekday from the game's Days enum), the room, company, visible moodlets and who is addressing her. Finished sessions older than a day move out of the probe's capped telemetry folder into the helper's data folder as verified gzip files (`python -m domus_helper.telemetry_archive`, and every 6 hours from the bridge).

## Live hardening (DA6G)

The third session (2.11.2) added these. The atlas reads the game's own map of what each interaction does to each need: `Interaction._autonomy_ads`, the table the game's autonomy uses, read attribute by attribute without calling the game (`autonomy_ads`: stat, name, and up to four operations with amount and advertise). Any interaction trial ends 30 s after it finishes, including one shorter than the 10 s maintenance mark. A verdict names the needs that rose during it (`rose=hygiene 82->100->99`). Once our action has finished and no child of ours runs, the game's own autonomy on the same object (a toilet's flush, a distress reflex: toilet, flush, wash hands) is aftermath at once, not a rival; a late push with user intent (pie menu, script with user intent) is still a rival, while the game's own reactions (source SCRIPT or REACTION, such as a bad smell) are not. Preflight refuses the excluded E1 sofa, so the crawl never plans it. Every scan (atlas, tuned, preflight, food) ticks four times a second at the same 5 ms budget. The game acts on a Sim's body distress even with autonomy off; that is her body's own action, and the helper's interaction percepts say so (`origin`: native_autonomy, native_reaction, script, pie_menu, game). Preflight and the food scan list what an object offers through its components as well as its class tuning, so a served plate shows its eat (`generic_consume_food`); cooking serves the food, and eating it is a separate act. A refused trial names its code in the inbox reply.

Owner commands (also available through the local command inbox when the zone reaches RUNNING):

| Command | Stage | What it does |
|---|---|---|
| `ashley_e1.arm LAB_E1` / `ashley_e1.arm LAB_E1_FORK` | E1 | Arm an observation session |
| `ashley_e1.start` / `ashley_e1.stop` | E1 | Start and stop observation |
| `ashley_e1.inbox` | E1 | Fallback start for the independent 1 Hz local command inbox |
| `ashley_e1.status` | E1 | Report probe and inbox state |
| `ashley_e1.disarm` | E1 | Disarm the session |
| `ashley_e2.prepare <object_id>` | E2 | Prepare one sit experiment on an object |
| `ashley_e2.sit <token>` | E2 | Admit and push one prepared sit experiment |
| `ashley_e2.pause` | E2 | Push the probe's pause request |
| `ashley_e2.release` | E2 | Remove the probe's pause request |

The inbox starts automatically through the zone manager object-add callback when
a zone reaches RUNNING. `ashley_e1.inbox` is the fallback if automatic start is
unavailable. Automatic start still awaits live qualification.

The inbox uses UTF-8 JSON files in `AshleyE1Telemetry/cmd/inbox`, single-use
32-character lowercase hex ids, and expiry of at most 60 seconds. Replies are
published atomically in `cmd/outbox`; claimed inputs finish in `cmd/done`.
`status` works while unarmed; `sit_trial` calls prepare then sit in one tick,
with the existing admission checks. The inbox survives stop and disarm and
its alarm ends at the zone boundary.

Build and verification (pinned official CPython 3.7.0 x64):

```powershell
powershell -ExecutionPolicy Bypass -File sims-e1/tools/build.ps1 -Version 2.35.0
powershell -ExecutionPolicy Bypass -File sims-e1/tools/verify.ps1 -Version 2.35.0
```

E1 evidence (acceptance, adjudication and repairs) is under
`sims-e1/evidence/`; it moves to the Domus repository when that repository
exists.

## History: E1 read-only builds (1.0.x)

The E1 read-only probe was described by
`PROJECT_ASHLEY_SIMS4_EMBODIMENT_E0_E1_IMPLEMENTATION_READY_PLAN_V1_2a.md`.
Its last internal build was version `1.0.11`. Product-facing branding remains
`Embodiment 1.0.0`; `E1` is an internal engineering and stage identifier.
Version `1.0.11` is a bounded telemetry-truth correction on 1.0.10, which
passed first-load acceptance A-M
(`evidence/E1_ACCEPTANCE_2026-09-29_09/acceptance.md`). Presence rows now carry
the probe-owned armed snapshot in `attestation` (1.0.10 and earlier wrote the
save GUID into `snapshot_slot` and left `snapshot_guid` null); per-session
counters reset on every accepted ARM; and the game thread never lowers a
writer-owned counter. 1.0.11 itself still requires runtime requalification.

The 1.0.10 repair preserves the closed command, scheduler, callback, and
writer contracts while making the alarm owner weak-referenceable, passing the
approved `objects.ALL_HIDDEN_REASONS` constant, handling transient save-slot
and interaction-view absence without fabrication, and fail-closing before
`session_open` until the complete save GUID/slot/Sim identity triple exists.
It adds writer-owned logical cap accounting with bounded reconciliation and
failure-only stop/cancel observability. Product-facing branding remains
`Embodiment 1.0.0`.
Attended-session filesystem setup, inventory, active-file creation, writes,
flushes, reconciliation, rotation, and close are owned by the writer thread;
ARM remains nonblocking and does not treat the post-construction writer state
as a readiness proof; worker startup state is authoritative.

The V1.2a expression `TimeSpan(interval_in_real_seconds(1))` was falsified by
exact Sims 1.128 bytecode: `interval_in_real_seconds(1)` already returns a
`TimeSpan`, and the nested constructor raises `TypeError: must be real number,
not TimeSpan`. The corrected binding passes `interval_in_real_seconds(1)`
directly as the `time_span` argument. Architecture and bootstrap semantics are
unchanged; the `date_and_time.TimeSpan` required-import key remains closed and
is still recorded in the 19-key summary.

The target Sims 1.128 command transport lowercases ordinary string arguments
before the Python callback. Owner command documentation remains
`ashley_e1.arm LAB_E1` and `ashley_e1.arm LAB_E1_FORK`. The adapter accepts
only the closed native tokens `lab_e1` and `lab_e1_fork` and maps them to the
canonical semantic names. It does not apply generic case normalization or
aliases. Mixed-case and lowercase distinctions that the native transport does
not preserve cannot be recovered by the probe.

The 1.0.11 build used the same tooling with `-Version 1.0.11`.

`install.ps1` and `remove.ps1` are mechanical OD-4 tools. They require an
explicit Owner-confirmed Sims user-data root and a closed game. This repair
pass does not perform installation or runtime witnessing.

Raw telemetry and witness material stay outside Git. Historical diagnostic
evidence remains preserved under `sims-e1/evidence`.
