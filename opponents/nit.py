import sys, json
for line in sys.stdin:
    m=json.loads(line); t=m.get("type")
    if t=="action_request":
        l=m["legal_actions"]
        r={"type":"action","action":"check" if "check" in l else ("call" if m["to_call"]<=4 else "fold")}
    elif t=="discard_request": r={"type":"discard","card":min(m["hole_cards"],key=lambda c:"23456789TJQKA".index(c[0]))}
    elif t=="match_end": break
    else: continue
    print(json.dumps(r),flush=True)
