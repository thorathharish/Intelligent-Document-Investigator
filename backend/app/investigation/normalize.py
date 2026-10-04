"""Typed value normalisation (LLD section 12).

Used by the verifier to confirm that a claimed value is really stated in its quote, and to give
equal values the same key regardless of wording ("thirty (30) days" == "30 days" == "net 30").
"""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_UNITS_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALES = {"hundred": 100, "thousand": 1000}
_WORD = "|".join(sorted(list(_UNITS_NUM) + list(_SCALES), key=len, reverse=True))
_DIGITS = r"\d[\d,]*(?:\.\d+)?"
# a number: digits, or number words optionally followed by "(30)"
_NUMBER = rf"(?:(?:{_WORD})\b(?:[\s-]+(?:{_WORD})\b)*(?:\s*\(\s*{_DIGITS}\s*\))?|{_DIGITS})"

_QUANTITY_RE = re.compile(rf"(?<![\w.])(?P<num>{_NUMBER})(?:\s*-?\s*(?P<w1>[A-Za-z]+))?(?:\s+(?P<w2>[A-Za-z]+))?", re.I)
_NET_RE = re.compile(r"\bnet\s+(\d+)\b", re.I)
_PERCENT_RE = re.compile(rf"(?<![\w.])(?P<num>{_NUMBER})\s*(?:%|percent\b|per\s+cent\b)", re.I)

_CURRENCY = {
    "$": "USD", "us$": "USD", "usd": "USD", "dollar": "USD", "dollars": "USD",
    "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "£": "GBP", "gbp": "GBP", "pound": "GBP", "pounds": "GBP",
    "₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR", "rupee": "INR", "rupees": "INR",
}
_MULTIPLIER = {"k": 10**3, "m": 10**6, "million": 10**6, "billion": 10**9, "lakh": 10**5, "lakhs": 10**5,
               "crore": 10**7, "crores": 10**7}
_SUFFIX = r"(?:\s*(?P<suf>k|m|million|billion|lakhs?|crores?)\b)?"
_MONEY_PREFIX_RE = re.compile(rf"(?P<cur>US\$|USD|EUR|GBP|INR|Rs\.?|\$|€|£|₹)\s*(?P<amt>{_DIGITS}){_SUFFIX}", re.I)
_MONEY_SUFFIX_RE = re.compile(
    rf"(?P<amt>{_DIGITS}){_SUFFIX}\s*(?P<cur>USD|EUR|GBP|INR|dollars?|euros?|pounds?|rupees?)\b", re.I
)

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"])}
_MONTHS.update({name[:3]: number for name, number in list(_MONTHS.items())})
_MONTHS["sept"] = 9
_MONTH = "|".join(sorted(_MONTHS, key=len, reverse=True))
_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_DMY_RE = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH})\.?,?\s+(\d{{4}})\b", re.I)
_DATE_MDY_RE = re.compile(rf"\b({_MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I)

# negative cues are checked first ("not permitted" before "permitted")
_NEGATIVE_CUES = ["not permitted", "not allowed", "prohibited", "may not", "shall not"]
_POSITIVE_CUES = ["permitted", "allowed", "required", "may", "shall"]
_NEGATIVE_VALUES = {"no", "false"}
_POSITIVE_VALUES = {"yes", "true"}

_DAY_QUALIFIERS = {"business": "business day", "working": "business day", "calendar": "day"}
_ARTICLES = re.compile(r"^(the|a|an)\s+", re.I)
_NO_SCOPE = {"", "general", "all", "n/a", "none", "null"}


@dataclass(frozen=True)
class Normalized:
    key: str        # e.g. "quantity:30|day"
    display: str    # e.g. "30 days"
    family: str     # quantity | money | percent | date | boolean | text


def _num_str(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _words_to_number(text: str) -> Decimal | None:
    total, current, seen = 0, 0, False
    for token in re.split(r"[\s-]+", text.lower().strip()):
        if token in _UNITS_NUM:
            current += _UNITS_NUM[token]
            seen = True
        elif token in _SCALES:
            current = max(current, 1) * _SCALES[token]
            if _SCALES[token] >= 1000:
                total, current = total + current, 0
            seen = True
        elif token:
            return None
    return Decimal(total + current) if seen else None


def _to_number(text: str) -> Decimal | None:
    paren = re.search(rf"\(\s*({_DIGITS})\s*\)", text)
    raw = paren.group(1) if paren else text
    try:
        return Decimal(raw.replace(",", "").strip())
    except InvalidOperation:
        return _words_to_number(re.sub(r"\(.*?\)", "", text))


def _singular(word: str) -> str:
    w = word.lower()
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def parse_quantities(text: str) -> list[tuple[Decimal, str]]:
    """Every (number, unit) in the text. Weeks are converted to days; unit is '' when there is no noun."""
    found: list[tuple[Decimal, str]] = [(Decimal(m.group(1)), "day") for m in _NET_RE.finditer(text)]
    for m in _QUANTITY_RE.finditer(text):
        number = _to_number(m.group("num"))
        if number is None:
            continue
        w1, w2 = (m.group("w1") or "").lower(), (m.group("w2") or "").lower()
        if w1 in _DAY_QUALIFIERS and _singular(w2) == "day":
            unit = _DAY_QUALIFIERS[w1]
        else:
            unit = _singular(w1)
        if unit == "week":
            number, unit = number * 7, "day"
        found.append((number, unit))
    return found


def parse_money(text: str) -> list[tuple[str, Decimal]]:
    found = []
    for regex in (_MONEY_PREFIX_RE, _MONEY_SUFFIX_RE):
        for m in regex.finditer(text):
            currency = _CURRENCY.get(m.group("cur").lower())
            try:
                amount = Decimal(m.group("amt").replace(",", ""))
            except InvalidOperation:
                continue
            if currency:
                found.append((currency, amount * _MULTIPLIER.get((m.group("suf") or "").lower(), 1)))
    return found


def parse_percents(text: str) -> list[Decimal]:
    return [n for n in (_to_number(m.group("num")) for m in _PERCENT_RE.finditer(text)) if n is not None]


def parse_dates(text: str) -> list[str]:
    found = [f"{y}-{mo}-{d}" for y, mo, d in _DATE_ISO_RE.findall(text)]
    for d, month, y in _DATE_DMY_RE.findall(text):
        found.append(f"{int(y):04d}-{_MONTHS[month.lower()]:02d}-{int(d):02d}")
    for month, d, y in _DATE_MDY_RE.findall(text):
        found.append(f"{int(y):04d}-{_MONTHS[month.lower()]:02d}-{int(d):02d}")
    return found


def boolean_polarity(text: str, allow_bare: bool) -> str | None:
    """'yes' / 'no' / None. Bare yes/no/true/false count only for values, not for quotes."""
    lowered = " ".join(text.lower().split())
    if allow_bare and lowered in _NEGATIVE_VALUES:
        return "no"
    if allow_bare and lowered in _POSITIVE_VALUES:
        return "yes"
    if any(re.search(rf"\b{re.escape(cue)}\b", lowered) for cue in _NEGATIVE_CUES):
        return "no"
    if any(re.search(rf"\b{re.escape(cue)}\b", lowered) for cue in _POSITIVE_CUES):
        return "yes"
    return None


def _text_key(value: str) -> Normalized | None:
    cleaned = _ARTICLES.sub("", " ".join(re.sub(r"[^\w\s]", " ", value.lower()).split()))
    return Normalized(f"text:{cleaned}", value.strip(), "text") if cleaned else None


def normalize_value(value: str, value_type: str) -> Normalized | None:
    """Normalise a claimed value. Returns None for type 'none' or an empty value.

    A typed value that cannot be parsed falls back to a text key.
    """
    value = (value or "").strip()
    if not value or value_type == "none":
        return None
    if value_type in ("duration", "number"):
        quantities = parse_quantities(value)
        if quantities:
            number, unit = quantities[0]
            shown = f"{_num_str(number)} {unit}{'s' if unit and number != 1 else ''}".strip()
            return Normalized(f"quantity:{_num_str(number)}|{unit}", shown, "quantity")
    elif value_type == "money":
        money = parse_money(value)
        if money:
            currency, amount = money[0]
            return Normalized(f"money:{currency}|{_num_str(amount)}", f"{currency} {amount:,}", "money")
    elif value_type == "percent":
        percents = parse_percents(value) or [n for n in [_to_number(value)] if n is not None]
        if percents:
            return Normalized(f"percent:{_num_str(percents[0])}", f"{_num_str(percents[0])}%", "percent")
    elif value_type == "date":
        dates = parse_dates(value)
        if dates:
            y, m, d = dates[0].split("-")
            return Normalized(f"date:{dates[0]}", f"{int(d)} {_MONTH_ABBR[int(m) - 1]} {y}", "date")
    elif value_type == "boolean":
        polarity = boolean_polarity(value, allow_bare=True)
        if polarity:
            return Normalized(f"boolean:{polarity}", polarity.capitalize(), "boolean")
    return _text_key(value)


def quote_supports(normalized: Normalized, quote: str) -> bool:
    """True when the normalised value can be re-derived from the quote by code (LLD section 11, step 5)."""
    payload = normalized.key.split(":", 1)[1]
    if normalized.family == "quantity":
        number, unit = payload.split("|")
        return any(
            _num_str(n) == number and (not unit or not u or u == unit) for n, u in parse_quantities(quote)
        )
    if normalized.family == "money":
        return any(f"{c}|{_num_str(a)}" == payload for c, a in parse_money(quote))
    if normalized.family == "percent":
        return any(_num_str(n) == payload for n in parse_percents(quote))
    if normalized.family == "date":
        return payload in parse_dates(quote)
    if normalized.family == "boolean":
        return boolean_polarity(quote, allow_bare=False) == payload
    return True  # text values are not checked by code


def normalize_scope(scope: str | None) -> str | None:
    cleaned = " ".join((scope or "").lower().split())
    return None if cleaned in _NO_SCOPE else cleaned
