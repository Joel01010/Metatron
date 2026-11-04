import json
import sys
for line in sys.stdin:
    try:
        req = json.loads(line)
        if req.get("cmd") == "ping":
            out = {"id": req.get("id"), "ok": True, "result": req.get("params")}
        else:
            out = {"id": req.get("id"), "ok": False, "error": {"message": "bad cmd"}}
        print(json.dumps(out), flush=True)
    except Exception as e:
        print(json.dumps({"id": None, "ok": False, "error": {"message": str(e)}}), flush=True)
