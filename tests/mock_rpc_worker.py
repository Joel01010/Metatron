import json, sys
for line in sys.stdin:
    obj=json.loads(line)
    if 'id' not in obj:
        continue
    m=obj.get('method'); rid=obj['id']; p=obj.get('params') or {}
    if m=='initialize': result={"ok":True}
    elif m=='thread/start': result={"thread":{"id":"th1"}}
    elif m=='turn/start':
        result={"turn":{"id":"tu1"}}
        print(json.dumps({"method":"item/agentMessage/delta","params":{"delta":"hi"}}), flush=True)
        print(json.dumps({"id":999,"method":"item/commandExecution/requestApproval","params":{"command":"echo hi"}}), flush=True)
    else: result={}
    print(json.dumps({"id":rid,"result":result}), flush=True)
