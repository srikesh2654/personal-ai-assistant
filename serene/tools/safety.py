"""safety.py — the guardrail between SERENE and your filesystem.

Every tool that touches a path runs it through `resolve()` first. This does
two jobs:
  1. turns a convenient path ("Downloads", "~/Desktop") into a real absolute
     path, and
  2. refuses anything that escapes ALLOWED_ROOT — so a model (or a typo, or a
     "../../Windows/System32") can never wander into system files.

This is defense in depth: even once SERENE can delete things, she can only
ever do it inside the area you allowed.
"""
import os

from serene.config import ALLOWED_ROOT


def resolve(path):
    """Return a safe absolute path inside ALLOWED_ROOT, or raise
    PermissionError if the path tries to escape it."""
    expanded = os.path.expanduser(path)            # turn ~ into the home dir
    if not os.path.isabs(expanded):
        expanded = os.path.join(ALLOWED_ROOT, expanded)
    real = os.path.realpath(expanded)              # collapse .. and symlinks
    root = os.path.realpath(ALLOWED_ROOT)

    try:
        inside = os.path.commonpath([real, root]) == root
    except ValueError:
        inside = False                             # different drive => outside

    if not inside:
        raise PermissionError(
            f"'{path}' is outside SERENE's allowed area ({root}).")
    return real
