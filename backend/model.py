"""Experimental rugby union match model. Inputs must be calibrated from real match data."""
from __future__ import annotations
import math, random
from dataclasses import dataclass
from typing import Iterable

@dataclass
class Team:
    name: str
    elo: float
    tries_for: float
    tries_against: float
    penalty_goals_for: float = 1.0
    penalty_goals_against: float = 1.0

def elo_probability(rating_a: float, rating_b: float, home_advantage: float = 0.0) -> float:
    """Expected A score on the Elo logistic scale."""
    return 1.0 / (1.0 + 10.0 ** (-(rating_a + home_advantage - rating_b) / 400.0))

def update_elo(rating_a: float, rating_b: float, score_a: float, k: float = 24.0, home_advantage: float = 0.0) -> tuple[float, float]:
    """Update ratings after a match; score is 1 win, .5 draw, 0 loss."""
    expected = elo_probability(rating_a, rating_b, home_advantage)
    delta = k * (score_a - expected)
    return rating_a + delta, rating_b - delta

def _poisson(lam: float, rng: random.Random) -> int:
    threshold, product, count = math.exp(-max(0.01, lam)), 1.0, 0
    while product > threshold and count < 40:
        count += 1
        product *= rng.random()
    return count - 1

def expected_events(team: Team, opponent: Team, elo_edge: float) -> tuple[float, float]:
    """Estimate tries and penalty goals from per-match rates and opponent defence."""
    tries = math.sqrt(max(.05, team.tries_for) * max(.05, opponent.tries_against))
    tries *= math.exp(max(-250, min(250, elo_edge)) / 1800.0)
    penalties = math.sqrt(max(.05, team.penalty_goals_for) * max(.05, opponent.penalty_goals_against))
    return tries, penalties

def simulate_match(a: Team, b: Team, simulations: int = 20000, home_advantage: float = 0.0, seed: int | None = None) -> dict:
    """Simulate tries, conversions (team conversion rate 78%) and penalty goals.

    Drop goals are omitted in this baseline. A production model should estimate
    event rates from chronological match-level data and account for red cards,
    weather, venue, lineups and competition context.
    """
    if a.name == b.name:
        raise ValueError("Teams must be different")
    if simulations < 100 or simulations > 500_000:
        raise ValueError("simulations must be between 100 and 500000")
    rng = random.Random(seed)
    edge = a.elo + home_advantage - b.elo
    ta, pa = expected_events(a, b, edge / 2)
    tb, pb = expected_events(b, a, -edge / 2)
    wins_a = wins_b = draws = total_a = total_b = 0
    margins = []
    for _ in range(simulations):
        tries_a, tries_b = _poisson(ta, rng), _poisson(tb, rng)
        conv_a = sum(2 for _ in range(tries_a) if rng.random() < .78)
        conv_b = sum(2 for _ in range(tries_b) if rng.random() < .78)
        score_a = 5 * tries_a + conv_a + 3 * _poisson(pa, rng)
        score_b = 5 * tries_b + conv_b + 3 * _poisson(pb, rng)
        total_a += score_a; total_b += score_b; margins.append(score_a-score_b)
        if score_a > score_b: wins_a += 1
        elif score_b > score_a: wins_b += 1
        else: draws += 1
    margins.sort()
    return {"team_a": a.name, "team_b": b.name, "simulations": simulations,
            "win_a": wins_a/simulations, "draw": draws/simulations, "win_b": wins_b/simulations,
            "mean_points_a": total_a/simulations, "mean_points_b": total_b/simulations,
            "margin_q10": margins[int(.10*simulations)], "margin_q50": margins[int(.50*simulations)],
            "margin_q90": margins[int(.90*simulations)], "model_status": "experimental_unvalidated"}
