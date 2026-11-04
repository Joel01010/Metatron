from __future__ import annotations

import os
from collections.abc import Iterable, Mapping

SAFE_INHERITED_ENV = {
    "ALLUSERSPROFILE", "APPDATA", "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)",
    "COMMONPROGRAMW6432", "COMSPEC", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA",
    "NUMBER_OF_PROCESSORS", "OS", "PATH", "PATHEXT", "PROCESSOR_ARCHITECTURE",
    "PROCESSOR_IDENTIFIER", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
    "PROGRAMW6432", "SYSTEMDRIVE", "SYSTEMROOT", "TEMP", "TMP", "USERDOMAIN",
    "USERNAME", "USERPROFILE", "WINDIR", "LANG", "LC_ALL", "TERM",
}


def child_environment(
    *,
    extra: Mapping[str, str] | None = None,
    allow: Iterable[str] = (),
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an allowlisted child environment.

    Secrets such as *_API_KEY are not inherited unless explicitly named in
    ``allow``. This is intentionally stricter than copying os.environ.
    """
    src = dict(os.environ if source is None else source)
    allowed = SAFE_INHERITED_ENV | {str(x).upper() for x in allow}
    out = {k: v for k, v in src.items() if k.upper() in allowed}
    for k, v in (extra or {}).items():
        out[str(k)] = str(v)
    return out
