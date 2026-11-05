"""Tests for the preflop range tables, the opponent classifier and legality of decisions.

Run from the repo root:   python -m unittest discover -s tests -v
"""
import itertools
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import betting  # noqa: E402
import config  # noqa: E402
import opponent_model as om  # noqa: E402
import postflop  # noqa: E402
import preflop  # noqa: E402
import preflop_table as pt  # noqa: E402

RANKS = "23456789TJQKA"
DECK = [r + s for r in RANKS for s in "shdc"]
HAVE_DATA = pt.tables_loaded()


def hist(*acts):
    """hist(('opp','raise'), ('me','call')) -> preflop history entries."""
    return [{"street": "preflop", "actor": a, "action": b} for a, b in acts]


def req(**kw):
    base = dict(type="action_request", street="preflop", board=[], pot=3, my_bet=1, opp_bet=2,
                to_call=1, my_stack=199, opp_stack=198, legal_actions=["fold", "call", "raise"],
                min_raise=4, max_raise=200, raises_left=3, history=[])
    base.update(kw)
    return base


def state(hole, seat="button"):
    return SimpleNamespace(hole_cards=list(hole), seat=seat)


class TestWidthLogic(unittest.TestCase):
    def test_default_widths_without_model(self):
        self.assertEqual(preflop.estimate_width(0, None), 100.0)
        self.assertAlmostEqual(preflop.estimate_width(1, None), 40.0)
        self.assertAlmostEqual(preflop.estimate_width(2, None), 16.0)

    def test_fresh_model_matches_defaults(self):
        m = om.OpponentModel()
        self.assertAlmostEqual(preflop.estimate_width(1, m), 40.0)
        self.assertAlmostEqual(preflop.estimate_width(2, m), 16.0)

    def test_flags(self):
        old = (config.USE_RANGE_TABLES, config.USE_OPP_CLASSIFIER)
        try:
            config.USE_RANGE_TABLES = False
            self.assertEqual(preflop.estimate_width(2, None), 100.0)
            config.USE_RANGE_TABLES, config.USE_OPP_CLASSIFIER = True, False
            m = om.OpponentModel()
            m.open_chances, m.open_raises = 100, 100          # would be a maniac...
            self.assertAlmostEqual(preflop.estimate_width(1, m), 40.0)  # ...but classifier is off
        finally:
            config.USE_RANGE_TABLES, config.USE_OPP_CLASSIFIER = old

    def test_frequent_raiser_is_wide(self):
        m = om.OpponentModel()
        for _ in range(60):
            m.on_hand_result({"history": hist(("opp", "raise"))})
        self.assertGreaterEqual(m.open_width(), 80)
        self.assertGreaterEqual(m.preflop_width(2), 80)      # random raisers do not narrow
        self.assertEqual(m.style, "maniac")

    def test_low_frequency_alone_does_not_make_a_bot_tight(self):
        """15% raise rate but no showdown evidence yet: stay at/above the no-evidence floor."""
        m = om.OpponentModel()
        for i in range(60):
            m.on_hand_result({"history": hist(("opp", "raise" if i % 7 == 0 else "call"))})
        self.assertGreaterEqual(m.open_width(), config.PREFLOP_MIN_WIDTH_NO_EVIDENCE)

    def test_evidence_separates_random_from_tight(self):
        rnd = random.Random(1)
        rand_raiser, tight = om.OpponentModel(), om.OpponentModel()
        for m in (rand_raiser, tight):
            m.open_chances, m.open_raises = 100, 15           # identical 15% raise frequency
            m.hands_observed = 100
        rand_raiser.raised_pcts = [rnd.random() for _ in range(30)]
        tight.raised_pcts = [0.86 + 0.14 * rnd.random() for _ in range(30)]
        self.assertGreaterEqual(rand_raiser.open_width(), 55)
        self.assertLessEqual(tight.open_width(), 25)
        self.assertEqual(rand_raiser.style, "random_raiser")
        self.assertEqual(tight.style, "tight")

    def test_evidence_is_collected_from_showdowns(self):
        m = om.OpponentModel()
        saved = om._pt
        try:
            om._pt = SimpleNamespace(get_percentile=lambda cards: 0.9)
            msg = {"history": hist(("opp", "raise"), ("me", "call")), "result": "showdown",
                   "opp_hole_cards": ["As", "Kd"], "opp_discard": "2c"}
            m.on_hand_result(msg)
            self.assertEqual(m.raised_pcts, [0.9])
            # no evidence when they did not raise, or when cards are missing
            m.on_hand_result({"history": hist(("opp", "call")), "opp_hole_cards": ["As", "Kd"], "opp_discard": "2c"})
            m.on_hand_result({"history": hist(("opp", "raise")), "opp_hole_cards": None, "opp_discard": "2c"})
            self.assertEqual(len(m.raised_pcts), 1)
        finally:
            om._pt = saved

    def test_model_never_raises_on_garbage(self):
        m = om.OpponentModel()
        for bad in ({}, {"history": None}, {"history": [None]}, {"history": [{"street": "preflop"}]},
                    {"history": "x"}, {"opp_hole_cards": 5}):
            m.on_hand_result(bad)
        m.on_discard_result(None, None, None)
        self.assertGreater(m.preflop_width(3), 0)


@unittest.skipUnless(HAVE_DATA, "preflop_data.py not generated yet")
class TestTables(unittest.TestCase):
    def test_every_hand_has_a_key(self):
        random_level = pt._LEVELS[100]
        missing = [c for c in itertools.combinations(DECK, 3) if pt.canonical_3card(list(c)) not in random_level]
        self.assertEqual(missing, [])
        self.assertEqual(len(random_level), 1755)

    def test_all_levels_complete(self):
        for lvl, table in pt._LEVELS.items():
            self.assertEqual(len(table), 1755, f"level {lvl}")
        self.assertEqual(len(pt._PCT), 1755)

    def test_interpolation_between_levels(self):
        lv = pt.levels()
        for lo, hi in zip(lv, lv[1:]):
            mid = (lo + hi) / 2.0
            for hand in (["As", "Kh", "Qd"], ["7s", "3h", "2d"], ["9s", "8s", "7s"]):
                a, b = pt.equity_at_width(hand, lo), pt.equity_at_width(hand, hi)
                m = pt.equity_at_width(hand, mid)
                self.assertAlmostEqual(m, (a + b) / 2.0, places=9)
        # clamped outside the range
        self.assertEqual(pt.equity_at_width(["As", "Kh", "Qd"], 1), pt.equity_at_width(["As", "Kh", "Qd"], lv[0]))
        self.assertEqual(pt.equity_at_width(["As", "Kh", "Qd"], 500), pt.equity_at_width(["As", "Kh", "Qd"], 100))

    def test_ordering(self):
        self.assertGreater(pt.get_percentile(["As", "Ah", "Ad"]), pt.get_percentile(["7s", "3h", "2d"]))
        self.assertGreater(pt.equity_at_width(["As", "Ah", "Ad"], 100), 0.7)

    def test_suit_isomorphism(self):
        a = pt.equity_at_width(["As", "Kh", "Qd"], 40)
        b = pt.equity_at_width(["Ac", "Kd", "Qs"], 40)
        self.assertEqual(a, b)


class TestFallback(unittest.TestCase):
    def test_missing_data_does_not_crash(self):
        tmp = tempfile.mkdtemp()
        try:
            for f in ("preflop_table.py", "config.py"):
                shutil.copy(SRC / f, tmp)
            code = ("import preflop_table as t; print(t.tables_loaded(), "
                    "round(t.equity_at_width(['As','Kh','Qd'], 40), 3), round(t.get_percentile(['As','Kh','Qd']), 3))")
            out = subprocess.run([sys.executable, "-c", code], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertTrue(out.stdout.startswith("False"))
            self.assertIn("preflop_data unavailable", out.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def assert_legal(tc, r, a):
    tc.assertEqual(a.get("type"), "action")
    tc.assertIn(a["action"], r["legal_actions"], f"{a} not legal in {r['legal_actions']}")
    if a["action"] == "raise":
        tc.assertIsInstance(a["amount"], int)
        tc.assertTrue(r["min_raise"] <= a["amount"] <= r["max_raise"], f"{a} outside [{r['min_raise']},{r['max_raise']}]")


class TestLegality(unittest.TestCase):
    SCENARIOS = {
        "button first action": (req(), "button"),
        "bb after limp": (req(my_bet=2, opp_bet=2, to_call=0, pot=4, my_stack=198, opp_stack=198,
                              legal_actions=["check", "raise"], raises_left=3,
                              history=hist(("opp", "call"))), "big_blind"),
        "bb facing min raise": (req(my_bet=2, opp_bet=4, to_call=2, pot=6, my_stack=198, opp_stack=196,
                                    min_raise=6, max_raise=200, raises_left=2,
                                    history=hist(("opp", "raise"))), "big_blind"),
        "bb facing 2.5x open": (req(my_bet=2, opp_bet=5, to_call=3, pot=7, my_stack=198, opp_stack=195,
                                    min_raise=8, raises_left=2, history=hist(("opp", "raise"))), "big_blind"),
        "button facing 3bet": (req(my_bet=5, opp_bet=13, to_call=8, pot=18, my_stack=195, opp_stack=187,
                                   min_raise=21, raises_left=1,
                                   history=hist(("me", "raise"), ("opp", "raise"))), "button"),
        "facing raise at the cap": (req(my_bet=13, opp_bet=40, to_call=27, pot=53, my_stack=187, opp_stack=160,
                                        legal_actions=["fold", "call"], min_raise=None, max_raise=None, raises_left=0,
                                        history=hist(("me", "raise"), ("opp", "raise"), ("me", "raise"), ("opp", "raise"))),
                                    "button"),
        "facing all-in (call/fold only)": (req(my_bet=2, opp_bet=200, to_call=198, pot=202, my_stack=198, opp_stack=0,
                                               legal_actions=["fold", "call"], min_raise=None, max_raise=None,
                                               raises_left=2, history=hist(("opp", "raise"))), "big_blind"),
        "facing all-in (min==max raise)": (req(my_bet=2, opp_bet=100, to_call=98, pot=102, my_stack=198, opp_stack=100,
                                               min_raise=200, max_raise=200, raises_left=2,
                                               history=hist(("opp", "raise"))), "big_blind"),
    }

    def test_all_scenarios_all_hands(self):
        rnd = random.Random(7)
        hands = [rnd.sample(DECK, 3) for _ in range(250)]
        hands += [["As", "Ah", "Ad"], ["2s", "3h", "7d"], ["As", "Ks", "Qs"]]
        for name, (r, seat) in self.SCENARIOS.items():
            for hole in hands:
                for model in (None, om.OpponentModel()):
                    a = preflop.decide(r, state(hole, seat), model)
                    assert_legal(self, r, a)

    def test_every_flag_combination_is_legal(self):
        saved = (config.USE_RANGE_TABLES, config.USE_OPP_CLASSIFIER)
        try:
            for rt, oc in itertools.product((True, False), repeat=2):
                config.USE_RANGE_TABLES, config.USE_OPP_CLASSIFIER = rt, oc
                for name, (r, seat) in self.SCENARIOS.items():
                    for hole in (["As", "Ah", "Ad"], ["2s", "7h", "9d"]):
                        assert_legal(self, r, preflop.decide(r, state(hole, seat), om.OpponentModel()))
        finally:
            config.USE_RANGE_TABLES, config.USE_OPP_CLASSIFIER = saved

    def test_missing_hole_cards_falls_back_safely(self):
        for name, (r, seat) in self.SCENARIOS.items():
            for st in (state([], seat), state(["As"], seat), None):
                assert_legal(self, r, preflop.decide(r, st, om.OpponentModel()))

    def test_missing_seat_is_inferred(self):
        r = req()
        st = SimpleNamespace(hole_cards=["As", "Kh", "Qd"], seat=None)
        self.assertEqual(preflop.infer_seat(r, st), "button")
        self.assertEqual(preflop.infer_seat(req(my_bet=2, opp_bet=2, to_call=0), st), "big_blind")
        self.assertEqual(preflop.infer_seat(req(history=hist(("opp", "raise"))), st), "big_blind")
        self.assertEqual(preflop.infer_seat(req(history=hist(("me", "raise"))), st), "button")

    @unittest.skipUnless(HAVE_DATA, "preflop_data.py not generated yet")
    def test_sanity_of_decisions(self):
        r, _ = self.SCENARIOS["button first action"]
        self.assertEqual(preflop.decide(r, state(["As", "Ah", "Ad"]), None)["action"], "raise")
        # at the cap with the nuts: call, never an illegal raise
        r, seat = self.SCENARIOS["facing raise at the cap"]
        self.assertEqual(preflop.decide(r, state(["As", "Ah", "Ad"], seat), None)["action"], "call")
        # junk facing an all-in: fold
        r, seat = self.SCENARIOS["facing all-in (call/fold only)"]
        self.assertEqual(preflop.decide(r, state(["2s", "3h", "7d"], seat), None)["action"], "fold")

    @unittest.skipUnless(HAVE_DATA, "preflop_data.py not generated yet")
    def test_wide_opponent_gets_called_more_than_tight_one(self):
        """Same hand, same price: calls a maniac's raise but not a very tight bot's re-raise."""
        r, seat = self.SCENARIOS["button facing 3bet"]
        wide, tight = om.OpponentModel(), om.OpponentModel()
        wide.open_chances = wide.open_raises = 100
        wide.hands_observed = 100
        tight.hands_observed = 100
        tight.open_chances, tight.open_raises = 100, 10
        tight.raised_pcts = [0.9 + 0.1 * random.Random(2).random() for _ in range(30)]
        calls = {"wide": 0, "tight": 0}
        rnd = random.Random(3)
        for _ in range(300):
            hole = rnd.sample(DECK, 3)
            for name, mdl in (("wide", wide), ("tight", tight)):
                if preflop.decide(r, state(hole, seat), mdl)["action"] != "fold":
                    calls[name] += 1
        self.assertGreater(calls["wide"], calls["tight"])


class TestRouter(unittest.TestCase):
    def test_routing(self):
        seen = []
        saved = (preflop.decide, postflop.decide)
        try:
            preflop.decide = lambda *a: seen.append("pre") or {"type": "action", "action": "check"}
            postflop.decide = lambda *a: seen.append("post") or {"type": "action", "action": "check"}
            betting.decide({"street": "preflop"}, None, None)
            for s in ("flop", "turn", "river"):
                betting.decide({"street": s}, None, None)
            self.assertEqual(seen, ["pre", "post", "post", "post"])
        finally:
            preflop.decide, postflop.decide = saved

    def test_postflop_baseline(self):
        self.assertEqual(postflop.decide({"legal_actions": ["check", "raise"]}, None, None)["action"], "check")
        self.assertEqual(postflop.decide({"legal_actions": ["fold", "call", "raise"]}, None, None)["action"], "call")
        self.assertEqual(postflop.decide({"legal_actions": ["fold"]}, None, None)["action"], "fold")


if __name__ == "__main__":
    unittest.main()
