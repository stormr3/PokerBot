import sys, csv, statistics, math

data = []
try:
    with open('c:/VSC_Projects/PokerBots/audit/decisions.csv', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['time_ms'] = float(row['time_ms'])
            row['pot'] = int(row['pot'])
            row['to_call'] = int(row['to_call'])
            row['hand_outcome_net'] = int(row['hand_outcome_net']) if row['hand_outcome_net'] else 0
            data.append(row)
except FileNotFoundError:
    print('decisions.csv not found yet')
    sys.exit(0)

print(f'Total rows: {len(data)}')

# bb/100 by seat
BB = 2
def bb100_from_rows(rows):
    if not rows: return float('nan')
    # group by hand
    hands = {}
    for r in rows:
        hid = r['hand_id']
        if hid not in hands:
            hands[hid] = {'seat': r['seat'], 'net': r['hand_outcome_net']}
    nets = [v['net'] for v in hands.values()]
    return sum(nets) / (len(nets) * BB / 100)

btn_rows = [r for r in data if r['seat'] == 'button']
bb_rows  = [r for r in data if r['seat'] == 'big_blind']
print(f'bb/100 as button: {bb100_from_rows(btn_rows):.1f}')
print(f'bb/100 as BB:     {bb100_from_rows(bb_rows):.1f}')

# Action frequencies by street
print('\nAction frequencies:')
for st in ['preflop','flop','discard','turn','river']:
    rows = [r for r in data if r['street'] == st]
    if not rows: continue
    acts = {}
    for r in rows:
        a = r['action_taken'].split(':')[0] if ':' in r['action_taken'] else r['action_taken']
        acts[a] = acts.get(a, 0) + 1
    total = sum(acts.values())
    print(f'  {st} (N={total}): ' + '  '.join(f'{k}={v}({100*v//total}%)' for k,v in sorted(acts.items())))

# Timing by street
print('\nTiming by street (ms):')
for st in ['preflop','flop','discard','turn','river']:
    times = [r['time_ms'] for r in data if r['street'] == st]
    if not times: continue
    times.sort()
    n = len(times)
    p95 = times[min(n-1, int(0.95*n))]
    print(f'  {st}: mean={statistics.mean(times):.1f} p95={p95:.1f} max={max(times):.1f} (N={n})')

# bet size histogram (non-call actions where amount is numeric)
print('\nRaise amounts (non-zero):')
raise_rows = [r for r in data if r['action_taken'] == 'raise' and r['amount']]
if raise_rows:
    sizes = [int(r['amount']) for r in raise_rows if r['amount'].isdigit()]
    pots  = [r['pot'] for r in raise_rows if r['amount'].isdigit()]
    fracs = [s/(max(1,p+s)) for s,p in zip(sizes, pots)]  # size as % of final pot
    if fracs:
        print(f'  Raise-to as %pot: mean={statistics.mean(fracs)*100:.1f}% min={min(fracs)*100:.1f}% max={max(fracs)*100:.1f}%')
        buckets = {'<40%':0, '40-60%':0, '60-80%':0, '80-100%':0, '>100%':0}
        for f in fracs:
            if f < 0.4: buckets['<40%'] += 1
            elif f < 0.6: buckets['40-60%'] += 1
            elif f < 0.8: buckets['60-80%'] += 1
            elif f <= 1.0: buckets['80-100%'] += 1
            else: buckets['>100%'] += 1
        for k, v in buckets.items():
            print(f'    {k}: {v} ({100*v//len(fracs)}%)')
