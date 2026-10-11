"""2.37.0 (W10 H3): game text that came with tokens, in words for her. The game's strings keep their tokens:
{0.SimFirstName} is a name, {M0.he}{F0.she} is a gender pair, {1.Number} is a count. Her view says the words.

One formatter, applied where the game's text keys are resolved for her view (Words, which the bridge gives the
observation builder and the extractor). Never raises: a token it does not know is dropped."""
import re

SOMEONE = "someone"
SOME = "some"
_TOKEN = re.compile(r"\{([^{}]*)\}")
_PAIR = re.compile(r"\{M(\d+)\.([^{}]*)\}\{F\1\.([^{}]*)\}")
_NAME = re.compile(r"\{(\d+)\.(SimFirstName|SimLastName|SimName|SimFullName)\}")
_NUMBER = re.compile(r"\{\d+\.Number\}")
_SPACES = re.compile(r"[ \t]{2,}")


def names_of(display):
    """The names of one Sim from its display name ("First Last"): {first, last, full}. None when there is no name
    (the probe says "someone" for a Sim it cannot name)."""
    if not isinstance(display, str) or display == SOMEONE:
        return None
    parts = display.split()
    if not parts:
        return None
    return {"first": parts[0], "last": parts[-1], "full": " ".join(parts)}


def fill(text, subject=None, gender=None, number=None):
    """The words of one game text. subject: the names of the Sim the text is about (names_of), or None for no one
    named (then a name token is "someone"). gender: "F" for the female form of a pair, anything else the first form.
    number: the count the row carries (a Number token is "some" without one). Other tokens are dropped."""
    if not isinstance(text, str):
        return None
    try:
        return _tidy(_fill(text, subject, gender, number))
    except Exception:
        return _tidy(_TOKEN.sub("", text))


def _fill(text, subject, gender, number):
    text = _PAIR.sub(lambda match: match.group(3) if gender == "F" else match.group(2), text)

    def name(match):
        # Token 0 is the Sim the text is about (her, in her own lines); a higher index is another Sim: someone.
        if subject is None or match.group(1) != "0":
            return SOMEONE
        field = match.group(2)
        if field == "SimFirstName":
            return subject["first"]
        if field == "SimLastName":
            return subject["last"]
        return subject["full"]
    text = _NAME.sub(name, text)
    text = _NUMBER.sub(lambda match: SOME if number is None else str(number), text)
    return _TOKEN.sub("", text)


def _tidy(text):
    return _SPACES.sub(" ", text).strip()


class Words(object):
    """2.37.0 (W10 H3): the game's text for a key, in words for her. The bridge sets her names (her) from her body
    row. words(key) is text about her (token 0 is her, a higher index is someone); words.other(key) is text about no
    one she can name (someone); words.raw(key) keeps the tokens. The probe does
    not report gender, so the first form of a pair is used (gender stays None until it does)."""

    def __init__(self, raw):
        self._raw = raw
        self.her = None
        self.gender = None

    def __call__(self, key):
        return self._words(key, self.her)

    def other(self, key):
        return self._words(key, None)

    def raw(self, key):
        """The game's text as it is, tokens kept: for act texts, which acts.clean_text fills with the target's name."""
        if self._raw is None:
            return None
        try:
            return self._raw(key)
        except Exception:
            return None

    def _words(self, key, subject):
        if self._raw is None:
            return None
        try:
            text = self._raw(key)
        except Exception:
            return None
        return fill(text, subject=subject, gender=self.gender)
