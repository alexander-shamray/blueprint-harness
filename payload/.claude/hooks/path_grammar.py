r"""Windows' other path grammar, which a hook must not open on a proposed call's behalf.

A hook runs before the permission prompt, so opening `//host/share` offers that host the user's NTLM response
whatever the user answers: `docs/harness-boundaries.md`, *Paths on another machine*.
"""

import os

# A name rather than `os.name` read in place, so a suite on POSIX can judge the Windows grammar by setting it.
WINDOWS = os.name == "nt"


def other_grammar(path):
    r"""Whether `path` is spelled in Windows' non-drive grammar: a UNC share, or a `\\?\` or `\\.\` prefix.

    The whole family is matched by its two leading separators, either way round, rather than by a list of prefixes,
    which would miss one. Scoped to Windows because `//x` on POSIX is an ordinary local path.
    """
    return WINDOWS and os.fspath(path)[:2].replace("/", "\\") == "\\\\"


def foreign(path, *own):
    r"""Whether `path` is in the other grammar and beneath none of the home and `own`, the places the session stands.

    A home or a checkout on a share is the user's own, which the session reaches already; a model can name any
    other. Compared lexically, so an alias of an own place, `\\?\UNC\host\…` for `\\host\…`, is foreign.
    """
    if not other_grammar(path):
        return False
    placed = os.path.normcase(os.path.normpath(os.fspath(path)))
    for root in (os.path.expanduser("~"), os.environ.get("HOME"), *own):
        if not root or not other_grammar(root):
            continue
        base = os.path.normcase(os.path.normpath(os.fspath(root)))
        if placed == base or placed.startswith(base.rstrip(os.sep) + os.sep):
            return False
    return True
