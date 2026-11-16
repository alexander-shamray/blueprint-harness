r"""Windows' other path grammar, which a hook must not open on a proposed call's behalf.

A hook runs before the permission prompt, so opening `//host/share` offers that host the user's NTLM response
whatever the user answers: `docs/harness-boundaries.md`, *Paths on another machine*.
"""

import ntpath
import os

# A name rather than `os.name` read in place, so a suite on POSIX can judge the Windows grammar by setting it.
WINDOWS = os.name == "nt"


def other_grammar(path):
    r"""Whether `path` is in Windows' non-drive grammar: a UNC share, `\\?\`, `\\.\`, or the NT namespace's `\??\`.

    Matched by two leading separators, either way round, rather than a list of prefixes, which would miss one; Win32
    passes `\??\` through as it is. Windows alone, because `//x` on POSIX is an ordinary local path."""
    text = os.fspath(path).replace("/", "\\")
    return WINDOWS and (text[:2] == "\\\\" or text[:4] == "\\??\\")


def foreign(path, *own):
    r"""Whether `path` is in the other grammar and beneath none of the home and `own`, the places the session stands.

    A home or a checkout on a share is the user's own, which the session reaches already; a model can name any
    other. Compared lexically and as Windows compares, so an alias of an own place, `\\?\UNC\host\…`, is foreign.
    """
    if not other_grammar(path):
        return False
    placed = ntpath.normcase(ntpath.normpath(os.fspath(path)))
    for root in (os.path.expanduser("~"), os.environ.get("HOME"), *own):
        if not root or not other_grammar(root):
            continue
        base = ntpath.normcase(ntpath.normpath(os.fspath(root)))
        if placed == base or placed.startswith(base.rstrip("\\") + "\\"):
            return False
    return True
