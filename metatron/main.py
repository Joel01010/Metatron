from __future__ import annotations

import json
import sys

from .core import Metatron
from .server import Dispatcher, ProtocolError


def main() -> int:
    app = Metatron()
    dispatcher = Dispatcher(app)
    try:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            rid = None
            try:
                req = json.loads(raw)
                rid = req.get("id")
                result = dispatcher.dispatch(str(req.get("cmd") or ""), req.get("params") or {})
                out = {"id": rid, "ok": True, "result": result}
            except ProtocolError as e:
                out = {"id": rid, "ok": False, "error": {"code": e.code, "message": str(e)}}
            except Exception as e:
                out = {"id": rid, "ok": False, "error": {"code": "internal", "message": str(e)}}
            sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
