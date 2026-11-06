import sys, json, random
for line in sys.stdin:
    m=json.loads(line); t=m.get("type")
    if t=="action_request":
        l=m["legal_actions"]; a=random.choice(l)
        r={"type":"action","action":a}
        if a=="raise": r["amount"]=random.randint(m["min_raise"],min(m["max_raise"],m["min_raise"]+30))
    elif t=="discard_request": r={"type":"discard","card":random.choice(m["hole_cards"])}
    elif t=="match_end": break
    else: continue
    print(json.dumps(r),flush=True)
