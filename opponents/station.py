import sys, json
for line in sys.stdin:
    m=json.loads(line); t=m.get("type")
    if t=="action_request": r={"type":"action","action":"check" if "check" in m["legal_actions"] else "call"}
    elif t=="discard_request": r={"type":"discard","card":min(m["hole_cards"],key=lambda c:"23456789TJQKA".index(c[0]))}
    elif t=="match_end": break
    else: continue
    print(json.dumps(r),flush=True)
