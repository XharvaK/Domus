"""Pure, closed command-inbox wire protocol."""
import json

COMMANDS = ('arm', 'start', 'stop', 'disarm', 'prepare', 'sit', 'pause',
            'release', 'status', 'sit_trial', 'atlas_dump', 'tuned_scan',
            'calibrate', 'trial', 'preflight', 'food_scan', 'situation_scan', 'act', 'answer',
            'cancel', 'camera', 'talk', 'pace', 'menu_near')
CODES = ('TOO_LARGE', 'BAD_JSON', 'BAD_SHAPE', 'BAD_VERSION', 'BAD_ID',
         'REPLAYED', 'EXPIRED', 'NOT_YET_VALID', 'TTL_TOO_LONG', 'BAD_ISSUER',
         'UNKNOWN_COMMAND', 'BAD_ARGS')
KEYS = {'v', 'id', 'issued_at_ms', 'expires_at_ms', 'issuer', 'command', 'args'}
# 2.31.0 (DOMUS_DEEP_DESIGN §11): the answer's arguments; rows and text are optional extras.
ANSWER_KEYS = {'act_id', 'dialog_id', 'pick', 'rows', 'text'}
FIELD_NAME_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-'


def _digits(value):
    return (type(value) is str and 1 <= len(value) <= 20 and
            all(ch in '0123456789' for ch in value))


def _pace_factor(value):
    """2.31.0 (W3p): a pace factor is a number (not a bool) from 0.25 to 1.0; 1.0 is normal pace."""
    return type(value) in (int, float) and 0.25 <= value <= 1.0


def _answer_rows(rows):
    """2.31.0: 1..16 picked rows, each {option_id: digits, count: 1..99}."""
    return (type(rows) is list and 1 <= len(rows) <= 16 and all(
        type(row) is dict and set(row) == {'option_id', 'count'} and _digits(row['option_id']) and
        type(row['count']) is int and 1 <= row['count'] <= 99 for row in rows))


def _answer_text(text):
    """2.31.0: 1..8 text fields, each name 1..32 of [A-Za-z0-9_.-] and a value of at most 256 characters."""
    return (type(text) is dict and 1 <= len(text) <= 8 and all(
        type(name) is str and 1 <= len(name) <= 32 and all(ch in FIELD_NAME_CHARS for ch in name) and
        type(value) is str and len(value) <= 256 for name, value in text.items()))


def valid_hex(value, length):
    return (type(value) is str and len(value) == length and
            all(ch in '0123456789abcdef' for ch in value))


# 2.40.0 (W13 P2, home): her save, her home edits and the catalogue dump. Each takes an act id (catalog_dump takes
# none); a place names one relation (on, beside or instead with a target; wall or in with a room), and an optional facing.
HOME_COMMANDS = ('save', 'buy', 'place', 'move', 'sell', 'catalog_dump')
COMMANDS = COMMANDS + HOME_COMMANDS
HOME_MAX_PRICE = 10 ** 12
PLACE_KEYS = {'rel', 'target_id', 'room_id', 'facing'}


def _place_ok(place):
    """2.40.0: a place: {rel, target_id} for on, beside or instead; {rel, room_id} for wall or in; facing (an object id
    or 'room') optional. Digits only for ids."""
    if type(place) is not dict or not set(place) <= PLACE_KEYS or 'rel' not in place:
        return False
    rel = place['rel']
    if rel in ('on', 'beside', 'instead'):
        need = {'rel', 'target_id'}
    elif rel in ('wall', 'in'):
        need = {'rel', 'room_id'}
    else:
        return False
    if not need <= set(place) or not set(place) <= need | {'facing'}:
        return False
    if not all(_digits(place[key]) for key in need - {'rel'}):
        return False
    if 'facing' not in place:
        return True
    return place['facing'] == 'room' or _digits(place['facing'])


def _home_args(name, args):
    """2.40.0: the arguments of a home command, by name (True when they are the closed shape)."""
    if name == 'catalog_dump':
        return not args
    if type(args) is not dict or not valid_hex(args.get('act_id'), 32):
        return False
    if name == 'save':
        return set(args) == {'act_id'}
    if name == 'sell':
        return set(args) == {'act_id', 'object_id'} and _digits(args['object_id'])
    if name in ('place', 'move'):
        return (set(args) == {'act_id', 'object_id', 'place'} and _digits(args['object_id']) and
                _place_ok(args['place']))
    if name == 'buy':
        keys = set(args)
        if not {'act_id', 'definition_id', 'place'} <= keys or not keys <= {'act_id', 'definition_id', 'place',
                                                                          'max_price'}:
            return False
        price = args.get('max_price')
        if 'max_price' in args and not (type(price) is int and 0 <= price <= HOME_MAX_PRICE):
            return False
        return _digits(args['definition_id']) and _place_ok(args['place'])
    return False


def valid_issuer(value):
    if type(value) is not str:
        return False
    if value in ('helper', 'console'):
        return True
    return (value.startswith('agent:') and 1 <= len(value[6:]) <= 34 and
            all(ch in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for ch in value[6:]))


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_object)


def parse(raw_bytes, now_ms, used_ids):
    if len(raw_bytes) > 4096:
        return None, 'TOO_LARGE'
    try:
        cmd = decode(raw_bytes)
    except (ValueError, UnicodeError, RecursionError):
        return None, 'BAD_JSON'
    if type(cmd) is not dict or set(cmd) != KEYS:
        return None, 'BAD_SHAPE'
    if type(cmd['v']) is not int or cmd['v'] != 1:
        return None, 'BAD_VERSION'
    if not valid_hex(cmd['id'], 32):
        return None, 'BAD_ID'
    if cmd['id'] in used_ids:
        return None, 'REPLAYED'
    issued, expires = cmd['issued_at_ms'], cmd['expires_at_ms']
    if type(issued) is not int or type(expires) is not int:
        return None, 'BAD_SHAPE'
    if now_ms > expires:
        return None, 'EXPIRED'
    if now_ms < issued:
        return None, 'NOT_YET_VALID'
    if expires - issued > 60000:
        return None, 'TTL_TOO_LONG'
    if not valid_issuer(cmd['issuer']):
        return None, 'BAD_ISSUER'
    if type(cmd['command']) is not str or cmd['command'] not in COMMANDS:
        return None, 'UNKNOWN_COMMAND'
    name, args = cmd['command'], cmd['args']
    good = type(args) is dict
    if good and name == 'arm':
        good = set(args) == {'name'} and args['name'] in ('lab_e1', 'lab_e1_fork')
    elif good and name in ('prepare', 'sit_trial'):
        good = (set(args) == {'object_id'} and type(args['object_id']) is str and
                1 <= len(args['object_id']) <= 20 and
                all(ch in '0123456789' for ch in args['object_id']))
    elif good and name == 'sit':
        good = set(args) == {'token'} and valid_hex(args['token'], 16)
    elif good and name == 'trial':
        good = (set(args) == {'object_id', 'guid64'} and
                _digits(args.get('object_id')) and _digits(args.get('guid64')))
    elif good and name == 'act':
        # 2.24.0: owner is present (and true) only when her Thought said the User asked for it.
        # 2.39.0 (W12 G1): variant is present only for a pie-menu choice: an int from 0 to 999.
        good = (set(args) - {'owner', 'variant'} == {'act_id', 'object_id', 'guid64'} and
                valid_hex(args.get('act_id'), 32) and _digits(args.get('object_id')) and
                _digits(args.get('guid64')) and ('owner' not in args or args['owner'] is True) and
                ('variant' not in args or (type(args['variant']) is int and 0 <= args['variant'] <= 999)))
    elif good and name == 'answer':
        # 2.18.0: her answer to a game dialog: a picker row (digits) or a button by name.
        # 2.31.0: optional rows (several picked rows, each with its count) and text (one value per
        # field); with either, pick is ok.
        pick = args.get('pick')
        good = (set(args) <= ANSWER_KEYS and {'act_id', 'dialog_id', 'pick'} <= set(args) and
                valid_hex(args.get('act_id'), 32) and _digits(args.get('dialog_id')) and (_digits(pick) or (
                    type(pick) is str and 1 <= len(pick) <= 16 and
                    all(ch in 'abcdefghijklmnopqrstuvwxyz_0123456789' for ch in pick))) and
                (set(args) == {'act_id', 'dialog_id', 'pick'} or (
                    pick == 'ok' and ('rows' not in args or _answer_rows(args['rows'])) and
                    ('text' not in args or _answer_text(args['text'])))))
    elif good and name == 'cancel':
        # 2.20.0: she stops one of her own actions, as the client's X on her queue does.
        good = (set(args) == {'act_id', 'interaction_id'} and valid_hex(args.get('act_id'), 32) and
                _digits(args.get('interaction_id')))
    elif good and name == 'camera':
        # 2.21.0: the overlay's camera follows her Sim or looks at one object; never the world.
        # 2.32.0 (HE14): unfollow keeps the view on her Sim and stops the game's follow (the User's hand on the controls).
        good = (set(args) == {'op', 'target_id'} and args.get('op') in ('follow_sim', 'focus_object', 'unfollow') and
                _digits(args.get('target_id')))
    elif good and name == 'talk':
        # 2.26.0: one line of social talk for the User's screen; text only, never an act.
        text = args.get('text')
        good = (set(args) in ({'text'}, {'text', 'sim_id'}) and type(text) is str and
                1 <= len(text) <= 240 and text.strip() == text and
                all(ch >= ' ' and ch != '\x7f' for ch in text) and
                ('sim_id' not in args or _digits(args['sim_id'])))
    elif good and name == 'pace':
        # 2.31.0 (W3p): her needs drain and the game's clock, as fractions of normal pace (1.0 is off).
        good = (set(args) == {'need_drain', 'slow_time'} and _pace_factor(args['need_drain']) and
                _pace_factor(args['slow_time']))
    elif good and name in HOME_COMMANDS:
        # 2.40.0 (W13 P2, home): her save, her home edits and the catalogue dump (home.py).
        good = _home_args(name, args)
    elif good:
        good = not args
    if not good:
        return None, 'BAD_ARGS'
    return cmd, None


def reply(id, status, code, result):
    return json.dumps(dict(id=id, status=status, code=code, result=result),
                      ensure_ascii=True, separators=(',', ':')).encode('utf-8')


def attribute_reply(payload, issuer):
    """Attach A12 attribution to the pump's reply; retain the four-field helper."""
    row = json.loads(payload.decode('utf-8'))
    row['issuer'] = issuer if valid_issuer(issuer) else None
    return json.dumps(row, ensure_ascii=True, separators=(',', ':')).encode('utf-8')
