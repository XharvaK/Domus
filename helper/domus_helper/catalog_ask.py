"""W13 (H): her catalogue asks, answered from the game's own catalogue.

Natalis hands an owed ask on the act round trip (`catalog: [{ask_id, words, max_price?, placement?}]`), once. The helper
searches the catalogue (catalog.search: purchasable furniture and decor, matched on words) and answers once:

    POST /domus/catalog  {v: 1, helper_session, ask_id, matched, items}

with at most 12 items, each {ref, id, name, price, placement, category}, the ref a `c` ref of this session. The search runs
on its own thread, off the bridge tick, as memory asks do. A room in an ask is not a filter here (the contract filters on
words, price and placement only).
"""
import logging
import threading
import time

log = logging.getLogger(__name__)

ASK_ID_LIMIT = 64
WORDS_LIMIT = 80
PLACEMENTS = ("floor", "wall", "surface")
ITEMS_SHOWN = 12
# A send that did not reach Natalis is tried once more after this long.
RETRY_WAIT_S = 5
# Ask ids this process has already answered (process-local, as the memory asks' are), oldest first, at most
# HANDLED_LIMIT of them; and the ids claimed whose answer is not sent yet (HELPER2-6).
HANDLED_LIMIT = 256
_HANDLED = {}
_PENDING = set()
_LOCK = threading.Lock()


def _ask(item):
    """(ask_id, words, max_price, placement) when the item is a well-formed ask, else None."""
    if not isinstance(item, dict):
        return None
    ask_id, words = item.get("ask_id"), item.get("words")
    if not isinstance(ask_id, str) or not 0 < len(ask_id) <= ASK_ID_LIMIT:
        return None
    if not isinstance(words, str) or not 0 < len(words.strip()) <= WORDS_LIMIT:
        return None
    max_price = item.get("max_price")
    max_price = max_price if type(max_price) is int and max_price >= 0 else None
    placement = item.get("placement") if item.get("placement") in PLACEMENTS else None
    return ask_id, words, max_price, placement


def _claim_new(asks):
    """The asks not answered yet and not being answered: each is claimed until its answer is sent or given up (HELPER2-6)."""
    if not isinstance(asks, list):
        return []
    fresh = []
    with _LOCK:
        for item in asks:
            ask = _ask(item)
            if ask is None or ask[0] in _HANDLED or ask[0] in _PENDING:
                continue
            _PENDING.add(ask[0])
            fresh.append(ask)
    return fresh


def _settle_claim(ask_id, sent):
    """An ask whose answer was sent is kept as answered; one that was not is released, and the next sync hands it again."""
    with _LOCK:
        _PENDING.discard(ask_id)
        if sent:
            _HANDLED[ask_id] = True
            while len(_HANDLED) > HANDLED_LIMIT:
                del _HANDLED[next(iter(_HANDLED))]


def answer_body(helper_session, ask_id, matched, items, refs):
    """The answer on the wire. items are catalog.search's; each gets its `c` ref in this session (refs is a RefBook)."""
    # Natalis's shape: a name 1 to 64 characters, a price (an integer), a placement of 1 to 16 characters or none, a
    # category of at most 40. An item that cannot take that shape is left out, never sent half-made.
    shown = []
    for item in items:
        name = item.get("name")
        if not isinstance(name, str) or not name.strip() or type(item.get("price")) is not int:
            continue
        placement = item.get("placement")
        shown.append({"ref": refs.ref(str(item["definition_id"]), prefix="c"), "id": str(item["definition_id"]),
                      "name": name[:64], "price": item["price"],
                      "placement": placement if isinstance(placement, str) and 1 <= len(placement) <= 16 else None,
                      "category": str(item.get("category") or "")[:40]})
        if len(shown) >= ITEMS_SHOWN:
            break
    return {"v": 1, "helper_session": helper_session, "ask_id": ask_id, "matched": int(matched), "items": shown}


def _answer(helper_session, ask_id, words, max_price, placement, search, refs):
    """The body for one ask. A search that fails answers nothing found, with no error text."""
    try:
        matched, items = search(words, max_price, placement)
    except Exception as error:
        log.warning("catalogue search for ask %s failed: %s", ask_id, type(error).__name__)
        matched, items = 0, []
    return answer_body(helper_session, ask_id, matched, items, refs)


def _send(client, ask_id, body):
    try:
        if client.post_catalog(body) is not None:
            return True
    except Exception as error:
        log.warning("catalogue answer %s not sent: %s", ask_id, type(error).__name__)
        return False
    log.warning("catalogue answer %s not sent", ask_id)
    return False


def _answer_all(asks, client, helper_session, search, refs):
    for ask_id, words, max_price, placement in asks:
        sent = False
        try:
            body = _answer(helper_session, ask_id, words, max_price, placement, search, refs)
            sent = _send(client, ask_id, body)
            if not sent:
                time.sleep(RETRY_WAIT_S)
                sent = _send(client, ask_id, body)
                if not sent:
                    log.warning("catalogue answer %s not sent after a retry", ask_id)
        finally:
            _settle_claim(ask_id, sent)


def handle_asks_in_background(asks, client, *, helper_session, refs, search, start=None):
    """Search and answer each new ask off the acts loop. The ids are claimed here, so a repeated sync never answers one
    twice; the search and the post run on a daemon thread. search(words, max_price, placement) gives (matched, items).
    Never raises."""
    fresh = _claim_new(asks)
    if not fresh:
        return
    run = lambda: _answer_all(fresh, client, helper_session, search, refs)
    if start is not None:
        start(run)
        return
    threading.Thread(target=run, name="domus-catalog", daemon=True).start()
