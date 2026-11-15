import sys, re, math
sys.path.insert(0,'c:/VSC_Projects/PokerBots/src')

def parse_log(path, our='A'):
    hands = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('#'):
                continue
            hid_m = re.match(r'#(\d+)\s+button\s+(\w+)', line)
            if not hid_m:
                continue
            hid = int(hid_m.group(1))
            btn = hid_m.group(2)
            our_seat = 'button' if btn == our else 'big_blind'
            result = 'fold' if '| fold ' in line else 'showdown'
            net_m = re.search(rf'\b{our}\s+([+-]\d+)', line)
            our_net = int(net_m.group(1)) if net_m else 0
            streets_found = {}
            for sm in re.finditer(r'(preflop|flop|turn|river):\s*((?:[AB][fcrx]\d*\s*)+)', line):
                st = sm.group(1)
                raw = sm.group(2).strip()
                acts = re.findall(r'([AB])([fcrx])(\d*)', raw)
                streets_found[st] = [(a, action, int(amt) if amt else 0) for a, action, amt in acts]
            last_street = 'preflop'
            for st in ['preflop','flop','turn','river']:
                if st in streets_found:
                    last_street = st
            hands.append({'hand_id': hid, 'btn': btn, 'seat': our_seat,
                          'result': result, 'net': our_net,
                          'streets': streets_found, 'last': last_street})
    return hands

logs = {
    'always_call': 'c:/VSC_Projects/PokerBots/audit/logs_call_101/match.log',
    'always_raise': 'c:/VSC_Projects/PokerBots/audit/logs_raise_101/match.log',
    'random_bot':  'c:/VSC_Projects/PokerBots/audit/logs_rand_303/match.log',
    'nit':         'c:/VSC_Projects/PokerBots/audit/logs_nit_101/match.log',
    'tight_raiser':'c:/VSC_Projects/PokerBots/audit/logs_tight_101/match.log',
}

for opp_name, log_path in logs.items():
    data = parse_log(log_path)
    total = len(data)
    btn = [h for h in data if h['seat']=='button']
    bb  = [h for h in data if h['seat']=='big_blind']
    def bb100(hs):
        if not hs: return 0
        return sum(h['net'] for h in hs) / (len(hs)*2/100)
    
    print(f"\n=== vs {opp_name} ({total} hands) ===")
    print(f"  btn bb/100={bb100(btn):.1f}  BB bb/100={bb100(bb):.1f}")
    
    # Action frequencies
    our_acts = {}
    opp_acts = {}
    for st in ['preflop','flop','turn','river']:
        our_acts[st] = {'r':0,'c':0,'f':0,'x':0,'total':0}
        opp_acts[st] = {'r':0,'c':0,'f':0,'x':0,'total':0}
    
    for h in data:
        for st, acts in h['streets'].items():
            if st not in our_acts:
                continue
            for player, action, amt in acts:
                target = our_acts if player=='A' else opp_acts
                if action in target[st]:
                    target[st][action] += 1
                target[st]['total'] += 1
    
    print("  Our actions (raise%/call%/check%/fold%):")
    for st in ['preflop','flop','turn','river']:
        a = our_acts[st]
        t = a['total']
        if t > 0:
            print(f"    {st}: r={100*a['r']//t}% c={100*a['c']//t}% x={100*a['x']//t}% f={100*a['f']//t}% (N={t})")
    
    # Last street distribution
    last_dist = {}
    for h in data:
        last_dist[h['last']] = last_dist.get(h['last'], 0) + 1
    print(f"  Last street: {last_dist}")
    
    # Showdown vs non-showdown
    sd = [h for h in data if h['result']=='showdown']
    nsd = [h for h in data if h['result']=='fold']
    if sd:
        print(f"  Showdown: {len(sd)} hands, net={sum(h['net'] for h in sd)}, win_rate={sum(1 for h in sd if h['net']>0)/len(sd)*100:.1f}%")
    if nsd:
        print(f"  Non-showdown: {len(nsd)} hands, net={sum(h['net'] for h in nsd)}")
