"""Pure, closed command-inbox wire protocol."""
import json

COMMANDS = ('arm', 'start', 'stop', 'disarm', 'prepare', 'sit', 'pause',
            'release', 'status', 'sit_trial', 'atlas_dump', 'tuned_scan',
            'calibrate', 'trial', 'preflight')
CODES = ('TOO_LARGE', 'BAD_JSON', 'BAD_SHAPE', 'BAD_VERSION', 'BAD_ID',
         'REPLAYED', 'EXPIRED', 'NOT_YET_VALID', 'TTL_TOO_LONG', 'BAD_ISSUER',
         'UNKNOWN_COMMAND', 'BAD_ARGS')
KEYS = {'v', 'id', 'issued_at_ms', 'expires_at_ms', 'issuer', 'command', 'args'}


def _digits(value):
    return (type(value) is str and 1 <= len(value) <= 20 and
            all(ch in '0123456789' for ch in value))


def valid_hex(value, length):
    return (type(value) is str and len(value) == length and
            all(ch in '0123456789abcdef' for ch in value))


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
