import re

# Unicode substitution table for normalizing text to ASCII-compatible forms.
#
# IMPORTANT: This table is empirically derived from characters observed in the
# NLM CDE repository text. It may be incomplete for future text sources.
# Characters not in this table will be stripped by the final encode/decode step.
#
# Categories covered:
#   - Control characters (C0/C1)
#   - Latin-1 Supplement (U+00A0-00FF)
#   - Latin Extended-A (U+0100-017F)
#   - Greek letters commonly used in scientific text
#   - General Punctuation (U+2000-206F): spaces, dashes, quotes
#   - Letterlike Symbols (U+2100-214F)
#   - Mathematical Operators (U+2200-22FF)
#   - Miscellaneous Symbols
#
UNICODE_SUBSTITUTIONS = {
    # === Control Characters (C0/C1) ===
    "\u0092": "",  # private use (often misencoded apostrophe)
    "\u0093": '"',  # private use (often misencoded left double quote)
    "\u0094": '"',  # private use (often misencoded right double quote)
    "\u0096": "",  # private use (often misencoded en dash)
    "\u0097": "",  # private use (often misencoded em dash)

    # === Latin-1 Supplement (U+00A0-00FF) ===
    "\u00a0": " ",  # non-breaking space
    "\u00a7": "section",  # section sign
    "\u00a9": "(C)",  # copyright
    "\u00ab": '"',  # left-pointing double angle quotation mark
    "\u00ad": "",  # soft hyphen (invisible)
    "\u00ae": "(R)",  # registered trademark
    "\u00b0": " degree ",  # degree sign
    "\u00b1": "+/-",  # plus-minus sign
    "\u00b2": "2",  # superscript 2
    "\u00b3": "3",  # superscript 3
    "\u00b5": "u",  # micro sign (µ)
    "\u00b7": "-",  # middle dot (interpunct)
    "\u00b9": "1",  # superscript 1
    "\u00bb": '"',  # right-pointing double angle quotation mark
    "\u00bc": "1/4",  # fraction one quarter
    "\u00bd": "1/2",  # fraction one half
    "\u00be": "3/4",  # fraction three quarters
    "\u00c9": "E",  # Latin E with acute
    "\u00d6": "O",  # Latin O with diaeresis
    "\u00d7": "x",  # multiplication sign
    "\u00d8": "O",  # Latin O with stroke (Norwegian)
    "\u00df": "ss",  # Latin sharp S (eszett) - correct ASCII form
    "\u00e0": "a",  # Latin a with grave
    "\u00e1": "a",  # Latin a with acute
    "\u00e2": "a",  # Latin a with circumflex
    "\u00e3": "a",  # Latin a with tilde
    "\u00e4": "a",  # Latin a with diaeresis
    "\u00e5": "a",  # Latin a with ring (Swedish)
    "\u00e6": "ae",  # Latin ae ligature
    "\u00e7": "c",  # Latin c with cedilla
    "\u00e8": "e",  # Latin e with grave
    "\u00e9": "e",  # Latin e with acute
    "\u00ea": "e",  # Latin e with circumflex
    "\u00eb": "e",  # Latin e with diaeresis
    "\u00ec": "i",  # Latin i with grave
    "\u00ed": "i",  # Latin i with acute
    "\u00ee": "i",  # Latin i with circumflex
    "\u00ef": "i",  # Latin i with diaeresis
    "\u00f0": "d",  # Latin eth (Icelandic)
    "\u00f1": "n",  # Latin n with tilde
    "\u00f2": "o",  # Latin o with grave
    "\u00f3": "o",  # Latin o with acute
    "\u00f4": "o",  # Latin o with circumflex
    "\u00f5": "o",  # Latin o with tilde
    "\u00f6": "o",  # Latin o with diaeresis
    "\u00f7": "/",  # division sign
    "\u00f8": "o",  # Latin o with stroke (Norwegian)
    "\u00f9": "u",  # Latin u with grave
    "\u00fa": "u",  # Latin u with acute
    "\u00fb": "u",  # Latin u with circumflex
    "\u00fc": "u",  # Latin u with diaeresis
    "\u00fd": "y",  # Latin y with acute
    "\u00fe": "th",  # Latin thorn (Icelandic)
    "\u00ff": "y",  # Latin y with diaeresis

    # === Latin Extended-A (U+0100-017F) ===
    "\u0152": "OE",  # Latin OE ligature
    "\u0153": "oe",  # Latin oe ligature
    "\u0160": "S",  # Latin S with caron
    "\u0161": "s",  # Latin s with caron
    "\u017d": "Z",  # Latin Z with caron
    "\u017e": "z",  # Latin z with caron

    # === Greek Letters (common in scientific/medical text) ===
    "\u0391": "Alpha",  # Greek capital Alpha
    "\u0392": "Beta",  # Greek capital Beta
    "\u0393": "Gamma",  # Greek capital Gamma
    "\u0394": "Delta",  # Greek capital Delta
    "\u03b1": "alpha",  # Greek alpha
    "\u03b2": "beta",  # Greek beta
    "\u03b3": "gamma",  # Greek gamma
    "\u03b4": "delta",  # Greek delta
    "\u03b5": "epsilon",  # Greek epsilon
    "\u03b6": "zeta",  # Greek zeta
    "\u03b7": "eta",  # Greek eta
    "\u03b8": "theta",  # Greek theta
    "\u03b9": "iota",  # Greek iota
    "\u03ba": "kappa",  # Greek kappa
    "\u03bb": "lambda",  # Greek lambda
    "\u03bc": "u",  # Greek mu (micro - used in concentrations)
    "\u03bd": "nu",  # Greek nu
    "\u03be": "xi",  # Greek xi
    "\u03c0": "pi",  # Greek pi
    "\u03c1": "rho",  # Greek rho
    "\u03c3": "sigma",  # Greek sigma
    "\u03c4": "tau",  # Greek tau
    "\u03c5": "upsilon",  # Greek upsilon
    "\u03c6": "phi",  # Greek phi
    "\u03c7": "chi",  # Greek chi
    "\u03c8": "psi",  # Greek psi
    "\u03c9": "omega",  # Greek omega

    # === General Punctuation (U+2000-206F) ===
    "\u2000": " ",  # en quad
    "\u2001": " ",  # em quad
    "\u2002": " ",  # en space
    "\u2003": " ",  # em space
    "\u2004": " ",  # three-per-em space
    "\u2005": " ",  # four-per-em space
    "\u2006": " ",  # six-per-em space
    "\u2007": " ",  # figure space
    "\u2008": " ",  # punctuation space
    "\u2009": " ",  # thin space
    "\u200a": " ",  # hair space
    "\u200b": "",  # zero-width space
    "\u200c": "",  # zero-width non-joiner
    "\u200d": "",  # zero-width joiner
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
    "\u2018": "'",  # left single quotation mark
    "\u2019": "'",  # right single quotation mark (apostrophe)
    "\u201a": "'",  # single low-9 quotation mark
    "\u201b": "'",  # single high-reversed-9 quotation mark
    "\u201c": '"',  # left double quotation mark
    "\u201d": '"',  # right double quotation mark
    "\u201e": '"',  # double low-9 quotation mark
    "\u201f": '"',  # double high-reversed-9 quotation mark
    "\u2020": "+",  # dagger (often used as footnote marker)
    "\u2021": "++",  # double dagger
    "\u2022": "-",  # bullet
    "\u2023": "-",  # triangular bullet
    "\u2024": ".",  # one dot leader
    "\u2025": "..",  # two dot leader
    "\u2026": "...",  # horizontal ellipsis
    "\u2027": "-",  # hyphenation point
    "\u202f": " ",  # narrow no-break space
    "\u2032": "'",  # prime (feet, minutes)
    "\u2033": '"',  # double prime (inches, seconds)
    "\u2039": "'",  # single left-pointing angle quotation mark
    "\u203a": "'",  # single right-pointing angle quotation mark

    # === Superscripts and Subscripts (U+2070-209F) ===
    "\u2070": "0",  # superscript 0
    "\u2074": "4",  # superscript 4
    "\u2075": "5",  # superscript 5
    "\u2076": "6",  # superscript 6
    "\u2077": "7",  # superscript 7
    "\u2078": "8",  # superscript 8
    "\u2079": "9",  # superscript 9
    "\u207a": "+",  # superscript plus
    "\u207b": "-",  # superscript minus
    "\u207f": "n",  # superscript n
    "\u2080": "0",  # subscript 0
    "\u2081": "1",  # subscript 1
    "\u2082": "2",  # subscript 2
    "\u2083": "3",  # subscript 3
    "\u2084": "4",  # subscript 4
    "\u2085": "5",  # subscript 5
    "\u2086": "6",  # subscript 6
    "\u2087": "7",  # subscript 7
    "\u2088": "8",  # subscript 8
    "\u2089": "9",  # subscript 9

    # === Letterlike Symbols (U+2100-214F) ===
    "\u2122": "(TM)",  # trademark sign

    # === Number Forms (U+2150-218F) ===
    "\u2153": "1/3",  # fraction one third
    "\u2154": "2/3",  # fraction two thirds
    "\u215b": "1/8",  # fraction one eighth
    "\u215c": "3/8",  # fraction three eighths
    "\u215d": "5/8",  # fraction five eighths
    "\u215e": "7/8",  # fraction seven eighths

    # === Mathematical Operators (U+2200-22FF) ===
    "\u2212": "-",  # minus sign
    "\u2217": "*",  # asterisk operator
    "\u2218": "o",  # ring operator
    "\u2219": "-",  # bullet operator
    "\u221a": "sqrt",  # square root
    "\u221e": "infinity",  # infinity
    "\u2228": "|",  # logical or
    "\u2229": "AND",  # intersection
    "\u222a": "OR",  # union
    "\u2248": "~=",  # almost equal to
    "\u2260": "!=",  # not equal to
    "\u2264": "<=",  # less than or equal to
    "\u2265": ">=",  # greater than or equal to

    # === Miscellaneous Symbols ===
    "\u25aa": "-",  # black small square (bullet-like)
    "\u25cf": "-",  # black circle (bullet-like)
    "\u25e6": "o",  # white bullet
    "\u2610": "[ ]",  # ballot box (unchecked)
    "\u2611": "[x]",  # ballot box with check
    "\u2612": "[x]",  # ballot box with x
    "\u2713": "[x]",  # check mark
    "\u2714": "[x]",  # heavy check mark
    "\u2715": "x",  # multiplication x
    "\u2716": "x",  # heavy multiplication x
    "\u2717": "x",  # ballot x
    "\u2718": "x",  # heavy ballot x

    # === Replacement Character ===
    "\ufffd": "",  # replacement character (invalid encoding)
}

_unicode_sub_re = re.compile(
    "|".join(re.escape(k) for k in UNICODE_SUBSTITUTIONS.keys())
)


def normalize_unicode(text: str) -> str:
    # First replace known substitutions
    def replace_match(match):
        return UNICODE_SUBSTITUTIONS[match.group(0)]

    text = _unicode_sub_re.sub(replace_match, text)

    # Then remove any remaining diacritics or odd encodings
    # e.g., é -> e, ü -> u, etc.
    text = text.encode("ascii", "ignore").decode("ascii")

    return text
