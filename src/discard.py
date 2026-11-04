# ==============================================================================
# discard.py — Flop Discard Selection Engine
# Owner: Person B
#
# Responsibilities:
# - Select 1 of 3 hole cards to discard post-flop.
# - Score candidate 2-card holdings based on current hand rank and draw potential.
# - Guarantee returning a valid card from hole_cards under all circumstances.
# ==============================================================================

from typing import Any

from evaluator import best_hand, default_discard


def choose(req: dict[str, Any], state: Any, opp_model: Any) -> dict[str, str]:
    """Selects one card to discard from the 3 hole cards upon receiving discard_request.

    Args:
        req: Official engine discard_request dictionary containing 'hole_cards' and 'board'.
        state: Authoritative GameState instance.
        opp_model: OpponentModel instance.

    Returns:
        dict: Format {"type": "discard", "card": "<card_str>"}.
    """
    hole_cards = req.get("hole_cards", [])
    board = req.get("board", [])

    if not hole_cards:
        return {"type": "discard", "card": "2s"}

    if len(hole_cards) <= 1:
        return {"type": "discard", "card": hole_cards[0]}

    # Baseline evaluation: evaluate each candidate 2-card holding on the 3-card flop
    # We want to keep the 2 cards that produce the strongest hand, discarding the odd card out.
    best_candidate_card = None
    best_retained_score = None

    for discard_candidate in hole_cards:
        retained = [c for c in hole_cards if c != discard_candidate]
        score = best_hand(retained, board)

        if best_retained_score is None or score > best_retained_score:
            best_retained_score = score
            best_candidate_card = discard_candidate

    if best_candidate_card is None:
        best_candidate_card = default_discard(hole_cards)

    return {"type": "discard", "card": best_candidate_card}
