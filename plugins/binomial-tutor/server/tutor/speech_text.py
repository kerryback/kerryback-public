"""Turns the tutor's streamed Markdown reply into sentences fit to speak.
Display math, code, tables, headings and list items are skipped: they go on the
whiteboard, not into speech.  Inline symbols and Markdown markers are dropped.
A "$" followed by a digit is a dollar amount and stays in the text.

Plain-text formulas in prose ("q = (1.02 - 0.9)/(1.1 - 0.9) = 0.6") are dropped too.
A formula is two or more operands joined by = + * / ^ < > and the like, or a
parenthesized group with an operator inside.  An operand is a number, a name of
one or two letters (with an optional _subscript), a parenthesized group, or a
call such as max(...).  A hyphen counts as minus only with spaces on both sides
or inside a group, so "risk-neutral", "two-period" and "and/or" stay, as do
"10%", "$5" and "q is 0.6".  Punctuation after a formula stays:
"So q = (1.02 - 0.9)/0.2, which is ..." is spoken "So, which is ...".

The tutor says formulas in words, so a lone "name = number" is a slip, not a
formula: "n = 3" is said "n equals 3" rather than dropped, which would leave a
hole ("between and").  A sentence left with no letters or digits is not
spoken, and neither is a sentence with "=" that is left with two words or fewer
("Find: σ = 0.0126 × √252 = ?"): the board shows it instead.

Decimals are written out the way the tutor should say them, because the speech
engine reads "9.44" as "nine, forty-four": 9.44 is "nine point forty-four",
0.6 is "zero point six", 1.02 is "one point oh two", and $5.88 is "five point
eighty-eight dollars"."""

import re

_END = re.compile(r"[.!?]+(?=\s)")                 # sentence end: not a decimal point
_LIST = re.compile(r"^\s*(?:\d+[.)]\s+)")          # numbered-list marker
_BOARD_LINE = re.compile(r"^\s*(?:#|[-*+]\s|\d+[.)]\s)")    # heading or list item: board only
_BLOCK_START = re.compile(r"^\s*>")                          # quote: a new spoken unit
_MAYBE_MARKER = re.compile(r"^\s*(?:\d+[.)]?|[-*+#>]+)?$")   # partial line that may become a marker
_SPECIAL = re.compile(r"[$`\n]")

_OP = r"(?:[=+*/^<>×÷−·≤≥≈≠]|\s-\s)"            # operator between operands
_IN_OP = r"(?:[=+*/^<>×÷−·≤≥≈≠,-])"              # inside a group: also unspaced minus and commas
_ATOM = r"(?:√?\$?\d+(?:[.,]\d+)*%?|√?(?<![\w'])[A-Za-zΔσμ][A-Za-z]?(?:_\w+)?(?![\w'])|\?)"


def _group(operand):
    """A parenthesized list of operands, optionally a call such as max(...)."""
    return rf"(?:\b[A-Za-z]+)?\(\s*-?{operand}(?:\s*{_IN_OP}\s*-?{operand})*\s*\)"


def _arith_group(operand):
    return rf"(?:\b[A-Za-z]+)?\(\s*-?{operand}(?:\s*{_IN_OP}\s*-?{operand})+\s*\)"


_OPERAND1 = rf"(?:{_group(_ATOM)}|{_ATOM})"
_OPERAND = rf"(?:{_group(_OPERAND1)}|{_ATOM})"   # groups nest one level
_FORMULA = re.compile(rf"-?{_OPERAND}(?:\s*{_OP}\s*-?{_OPERAND})+|{_arith_group(_OPERAND1)}")
# "n = 3" or "σ = 0.20" alone in a sentence: said as "n equals 3", not dropped.
_SIMPLE_EQ = re.compile(r"(?<![\w'])([A-Za-zΔσμ][A-Za-z]?)\s*=\s*(\$?\d+(?:\.\d+)?%?)(?!\w|\.\d|\s*[=+*/^×÷−·]|\s+-\s)")


def _say_simple_eq(s):
    def one(m):
        before = s[:m.start()].rstrip()
        if before and before[-1] in "=+*/^×÷−·-(":      # part of a longer formula
            return m.group(0)
        return f"{m.group(1)} equals {m.group(2)}"
    return _SIMPLE_EQ.sub(one, s)

_ITALIC = re.compile(r"(?<![\w*])([*_])(?=\S)([^*_\n]+?)(?<=\S)\1(?![\w*])")


_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
         "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def number_words(n: int) -> str:
    """0 <= n < 10**12 in words: 944 -> "nine hundred forty-four"."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return _ONES[n // 100] + " hundred" + (" " + number_words(n % 100) if n % 100 else "")
    for size, name in ((10**9, "billion"), (10**6, "million"), (1000, "thousand")):
        if n >= size:
            return number_words(n // size) + " " + name + (" " + number_words(n % size) if n % size else "")
    return str(n)


def decimal_words(whole: str, frac: str) -> str:
    """("9", "44") -> "nine point forty-four"; ("1", "02") -> "one point oh two".
    Three or more digits are read one by one: ("0", "0126") -> "zero point zero
    one two six"."""
    if len(frac) > 2:
        return f"{number_words(int(whole.replace(',', '')))} point " + " ".join(_ONES[int(c)] for c in frac)
    zeros = len(frac) - len(frac.lstrip("0"))
    rest = frac.lstrip("0")
    after = " ".join(["oh"] * zeros + ([number_words(int(rest))] if rest else []))
    return f"{number_words(int(whole.replace(',', '')))} point {after}"


_DECIMAL = re.compile(r"(?<![\w.])(-)?(\$)?(\d{1,3}(?:,\d{3})+|\d+)\.(\d+)(?![\w.]*\d)")


def _say_decimals(s):
    def one(m):
        minus, dollar, whole, frac = m.groups()
        words = decimal_words(whole, frac[:6])
        return ("minus " if minus else "") + words + (" dollars" if dollar else "")
    return _DECIMAL.sub(one, s)


def spoken_form(prose: str) -> str:
    """Return the text as it should be spoken, or "" if nothing is speakable."""
    s = re.sub(r"\$\$.*?\$\$", " ", prose, flags=re.S)
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"\$(?![\d\s])[^$]*\$", " ", s)       # inline math; "$5" is currency
    s = re.sub(r"\$(?!\d)|`", "", s)                  # stray leftovers
    s = re.sub(r"^[\s>]*(?:[-*+]\s+|\d+[.)]\s+)?", "", s)
    s = re.sub(r"\*\*|__", "", s)                     # bold markers
    s = _ITALIC.sub(r"\2", s)                         # italic markers, so "*q*" is not "q times"
    s = _say_simple_eq(s)
    s = _FORMULA.sub(" ", s)
    s = re.sub(r"[*_#]", "", s)
    s = s.replace("√", " the square root of ").replace("σ", " sigma ").replace("Δt", " delta t ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([.,;:!?])", r"\1", s)
    if "=" in prose and len(re.findall(r"[A-Za-z0-9]+", s)) <= 2:
        return ""                                     # a formula line ("Find: σ = ?"): the board shows it
    s = _say_decimals(s)
    s = re.sub(r"\s*%", " percent", s)
    return s if re.search(r"[A-Za-z0-9]", s) else ""


class SpeechStream:
    def __init__(self):
        self.buf = ""            # text not yet read
        self.pending = ""        # prose of the sentence in progress
        self.skip = None         # "$$" or "```" while inside a skipped block
        self.line_start = True   # True if buf begins at the start of a line

    def feed(self, delta: str) -> list[str]:
        self.buf += delta
        return self._run(final=False)

    def flush(self) -> list[str]:
        out = self._run(final=True)
        self._break(out)
        self.buf, self.skip, self.line_start = "", None, True
        return out

    def _run(self, final):
        out = []
        while self.buf:
            if self.skip:
                i = self.buf.find(self.skip)
                if i < 0:
                    self.buf = "" if final else self.buf[-2:]   # keep a possible half closer
                    break
                self.buf = self.buf[i + len(self.skip):]
                self.skip = None
                self.line_start = False
                continue
            if self.line_start:
                if not self._line_start(out, final):
                    break
                if self.line_start:     # a dropped row or blank line: check the next line too
                    continue
            if self.buf and not self._scan(out, final):
                break
        return out

    def _line_start(self, out, final):
        """Handle what the start of a line means.  False means wait for more text."""
        buf = self.buf
        if buf.lstrip(" \t").startswith("\n"):            # blank line
            self._break(out)
            self.buf = buf.lstrip(" \t")[1:]
            return True
        if buf.lstrip().startswith("|"):                  # table row
            self._break(out)
            if "\n" not in buf:
                if final:
                    self.buf = ""
                return False
            self.buf = buf[buf.index("\n") + 1:]
            return True
        if "\n" not in buf and _MAYBE_MARKER.match(buf) and not final:
            return False
        if _BOARD_LINE.match(buf):                         # heading or list item
            self._break(out)
            if "\n" not in buf:
                if final:
                    self.buf = ""
                return False
            self.buf = buf[buf.index("\n") + 1:]
            return True
        if _BLOCK_START.match(buf):
            self._break(out)
            self.buf = _LIST.sub("", buf)
        self.line_start = False
        return True

    def _scan(self, out, final):
        """Consume prose up to the next special character.  False means wait for more text."""
        buf = self.buf
        m = _SPECIAL.search(buf)
        if not m:
            self._add(buf, out)
            self.buf = ""
            return True
        i, ch = m.start(), m.group()
        self._add(buf[:i], out)
        rest = buf[i:]
        if ch == "\n":
            self._add(" ", out)
            self.buf, self.line_start = rest[1:], True
            return True
        if ch == "$":
            if rest.startswith("$$"):
                return self._open_block("$$", rest, out)
            if len(rest) == 1:
                return self._hold(rest, final)
            if rest[1].isdigit():                         # dollar amount
                self._add("$", out)
                self.buf = rest[1:]
                return True
            if not rest[1].isspace():
                close = rest.find("$", 1)
                nl = rest.find("\n")
                if close >= 0 and (nl < 0 or close < nl):  # inline math: drop it
                    self._add(" ", out)
                    self.buf = rest[close + 1:]
                    return True
                if nl < 0:
                    return self._hold(rest, final)
            self.buf = rest[1:]                           # stray "$"
            return True
        if rest.startswith("```"):
            return self._open_block("```", rest, out)
        if rest.startswith("``") and len(rest) == 2:
            return self._hold(rest, final)
        close = rest.find("`", 1)
        nl = rest.find("\n")
        if close >= 0 and (nl < 0 or close < nl):         # inline code: drop it
            self._add(" ", out)
            self.buf = rest[close + 1:]
            return True
        if nl < 0 and len(rest) >= 1 and not final:
            return self._hold(rest, final)
        self.buf = rest[1:]                               # stray backtick
        return True

    def _open_block(self, marker, rest, out):
        self._break(out)
        self.skip = marker
        self.buf = rest[len(marker):]
        return True

    def _hold(self, rest, final):
        self.buf = "" if final else rest
        return final

    def _add(self, text, out):
        self.pending += text
        pos = 0
        for m in _END.finditer(self.pending):
            self._emit(self.pending[pos:m.end()], out)
            pos = m.end()
        self.pending = self.pending[pos:]

    def _break(self, out):
        self._emit(self.pending, out)
        self.pending = ""

    @staticmethod
    def _emit(sentence, out):
        s = spoken_form(sentence)
        if s:
            out.append(s)
