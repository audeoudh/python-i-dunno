import enum
import unicodedata
from ipaddress import \
    IPv4Address, IPv6Address, ip_address, IPV6LENGTH, IPV4LENGTH
from typing import Union

from idna import intranges_contain

from . import tools

# TODO: here, while loading required data sets, we have to do at least 3 urlopen
#  requests.  One should implement a cache to preload them and load them faster
#  and without requiring an internet connexion.  See e.g. idna implementation.
emoji_ranges = tuple(tools.merge_ranges(tools.get_emoji_ranges()))
intranges_emoji = tuple((start << 32) | (end + 1)
                        for start, end, _ in emoji_ranges)
scripts_ranges = tuple(tools.merge_ranges(tools.get_scripts_ranges()))
scripts = set(script for _, _, script in scripts_ranges)
intranges_scripts = {
    script: tuple((start << 32) | (end + 1)
                  for start, end, s in scripts_ranges
                  if s == script)
    for script in scripts
}
confusables = tuple(tools.get_confusable())


# From & to I-DUNNO computations

def deform_i_dunno(s: str) -> Union[IPv4Address, IPv6Address]:
    """Compute an address from its I-DUNNO representation."""
    # v: integer representation of deformed I-DUNNO.
    v = 0
    # i: number of bits already encoded in the value v.
    i = 0
    for c in reversed(s):
        c = ord(c)
        # n: number of bits encoded by this code point
        n = 7 if c <= 0x7F else 11 if c <= 0x7FF else 16 if c <= 0xFFFF else 21
        v |= (c << i)
        i += n
    if 32 <= i < 52:
        kls = IPv4Address
    elif 128 <= i < 148:
        kls = IPv6Address
    else:
        raise ValueError("Wrong I-DUNNO address length")
    padding = i - (IPV4LENGTH if kls == IPv4Address else IPV6LENGTH)
    v >>= padding
    return kls(v)


def form_i_dunno(a, fmt) -> str:
    """Convert an address to its I-DUNNO form.

    :param a: The address to form.
    :param fmt: The required format: a list of count of bits to take for each
    code point (7, 11, 16 or 21) in the formed I-DUNNO.  The list must sum up
    to 128 for IPv6 and 32 for IPv4.
    :raise ValueError if the provided address and format does not reach the
    satisfactory Minimum Confusion Level.

    TODO: add a 'padding' parameter to allow providing the padding bits.
    TODO: guess format if fmt=None and try to reach Delightful Confusion Level.
    """
    a = ip_address(a)
    N = a.max_prefixlen  # number of bits in total
    a = int(a)
    r = ""  # result string
    i = 0  # number of bits already consumed in a
    if sum(fmt) != N:
        raise ValueError("Format should sum up to the number of bits")
    for n in fmt:  # n: number of bits to take for this code point.
        # Take n bit from the N-bits address from the position i, big endian.
        v = a >> (N - i - n) & (2 ** n - 1)
        # TODO: support (left-)padding
        r += chr(v)
        i += n
    if get_confusion_level(r) == ConfusionLevel.NONE:
        raise ValueError("The formed string does not reach the satisfactory Minimum Confusion Level")
    return r


# Confusion level calculation

class ConfusionLevel(enum.Enum):
    NONE = "none"
    MINIMUM = "minimum"
    SATISFACTORY = "satisfactory"
    DELIGHTFUL = "delightful"


def get_confusion_level(s):
    # Minimal
    m_sequence_bigger_than_one_octet = False
    m_disallowed = True
    # Satisfactory
    s_non_printable_char = False
    s_two_different_scripts = False
    s_symbol = False
    # Delightful
    d_different_directionalities = False
    d_confusable = False
    d_emoji = False
    # Compute conditions
    used_scripts = set()
    directionalities = set()
    for c in s:
        m_sequence_bigger_than_one_octet |= ord(c) > 0x7F
        # TODO: m_disallowed
        # FIXME: Cc is non-printable, but is Cf printable?
        s_non_printable_char |= unicodedata.category(c) in ("Cf", "Cc")
        s_symbol |= unicodedata.category(c).startswith("S")
        for script, intrange_script in intranges_scripts.items():
            if intranges_contain(ord(c), intrange_script):
                used_scripts.add(script)
                break
        else:
            raise ValueError(f"Unknown char script for char '{unicodedata.name(c)}' (U+{ord(c)})")
        directionalities.add(unicodedata.bidirectional(c))
        d_emoji |= intranges_contain(ord(c), intranges_emoji)
    s_two_different_scripts |= len(used_scripts) >= 2
    d_different_directionalities |= len(directionalities) >= 2
    for confusable in confusables:
        if confusable in s:
            d_confusable = True
            break
    # Compute level
    if m_sequence_bigger_than_one_octet and m_disallowed:
        if s_non_printable_char + s_two_different_scripts + s_symbol >= 2:
            if d_different_directionalities + d_confusable + d_emoji >= 2:
                return ConfusionLevel.DELIGHTFUL
            return ConfusionLevel.SATISFACTORY
        return ConfusionLevel.MINIMUM
    return ConfusionLevel.NONE


if __name__ == '__main__':
    import argparse

    def _test():
        # Testing with example provided in RFC
        a = IPv4Address("198.51.100.164")
        assert int(a) == 0b11000110001100110110010010100100
        d = form_i_dunno(a, [7, 7, 7, 11])
        assert d == "\u0063\u000C\u006C\u04A4"
        # Error in RFC, confirmed by authors: it is Delightful Confusion Level.
        assert get_confusion_level(d) == ConfusionLevel.DELIGHTFUL

    def _form(ip_address):
        print(form_i_dunno(ip_address, [7, 7, 7, 11]))  # TODO: fmt=None

    def _deform(i_dunno):
        print(deform_i_dunno(i_dunno))

    def _level(i_dunno):
        print(get_confusion_level(i_dunno).value)

    parser = argparse.ArgumentParser()
    sp = parser.add_subparsers(required=True)
    tp = sp.add_parser("test", help="Run the code on test vectors")
    tp.set_defaults(action=_test)
    fp = sp.add_parser("form", help="Form a I-DUNNO from the provided address")
    fp.add_argument("ip_address")
    fp.set_defaults(action=_form)
    dp = sp.add_parser("deform",
                       help="Deform a I-DUNNO.  May be use in automatically "
                            "(e.g. in scripts) to obtain original address, but "
                            "by definition humans should not attempt to use it "
                            "interactively.")
    dp.add_argument('i_dunno')
    dp.set_defaults(action=_deform)
    lp = sp.add_parser("level", help="Compute Confusion Level from a I-DUNNO.")
    lp.add_argument('i_dunno')
    lp.set_defaults(action=_level)

    args = parser.parse_args()
    action = args.action
    del args.action
    action(**vars(args))
