import sys
sys.path.insert(0,'c:/VSC_Projects/PokerBots/src')

from postflop import _choose, _size
from state import GameState
from opponent_model import OpponentModel
from bet_utils import can_raise

# Test bluff path with no raise option available
req_no_raise = {
    'legal_actions': ['check'],
    'pot': 10, 'to_call': 0, 'my_stack': 100, 'my_bet': 0,
    'opp_bet': 0, 'history': [], 'raises_left': 0,
    'min_raise': None, 'max_raise': None
}
state = GameState(); state.seat = 'button'
opp = OpponentModel()
# Set up high fold-to-bet -> triggers bluff code
opp.faced_bets = 20; opp.faced_folds = 15
opp.post_opps = 10; opp.post_bets = 4

can = can_raise(req_no_raise)
print(f'can_raise with no raise legal: {can}')

r = _choose(0.10, req_no_raise, 'flop', state, opp, False)
print(f'_choose result: {r}')
print(f'Is raise action returned when raise not legal: {r.get("action") == "raise"}')

# Now test with fold option only
req_fold_only = {
    'legal_actions': ['fold', 'call'],
    'pot': 10, 'to_call': 5, 'my_stack': 100, 'my_bet': 0,
    'opp_bet': 5, 'history': [], 'raises_left': 0,
    'min_raise': None, 'max_raise': None
}
r2 = _choose(0.10, req_fold_only, 'flop', state, opp, False)
print(f'Facing bet, e=0.10, no raise: {r2}')

# Check _size when canr is False (should not be called)
# But the question is: in line 136 of postflop.py, is canr checked?
# Let's check the actual code
with open('c:/VSC_Projects/PokerBots/src/postflop.py') as f:
    lines = f.readlines()
for i, l in enumerate(lines[130:140], start=131):
    print(f"Line {i}: {l}", end='')
