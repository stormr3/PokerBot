import sys, json, random
for line in sys.stdin:
    m=json.loads(line); t=m.get("type")
    if t=="action_request":
        l=m["legal_actions"]
        if "raise" in l and random.random()<0.7: r={"type":"action","action":"raise","amount":min(m["max_raise"],max(m["min_raise"],m["opp_bet"]+int(0.8*m["pot"])))}
        else: r={"type":"action","action":"call" if "call" in l else "check"}
    elif t=="discard_request": r={"type":"discard","card":min(m["hole_cards"],key=lambda c:"23456789TJQKA".index(c[0]))}
    elif t=="match_end": break
    else: continue
    print(json.dumps(r),flush=True)
