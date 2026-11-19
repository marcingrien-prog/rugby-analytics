#!/usr/bin/env python3
"""Fetch public rugbyAPI data and build the static payload served by GitHub Pages.

The API key is read only from the GitHub Actions environment. It is never
written to the generated JSON or exposed to the browser.
"""
from __future__ import annotations
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = "https://api.rugbyapi.com/v1"
OUT = Path("data/live-data.json")
TIMEOUT = 25
MAX_STANDINGS = 10


def api_get(path: str, key: str, params: dict | None = None) -> dict:
    response = requests.get(
        BASE + path,
        params=params,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected response from {path}")
    return payload


def logistic(value: float) -> float:
    value = max(-20.0, min(20.0, value))
    return 1.0 / (1.0 + math.exp(-value))

def normal_cdf(value: float, mean: float, sd: float) -> float:
    return 0.5 * (1.0 + math.erf((value - mean) / (sd * math.sqrt(2.0))))


def match_probabilities(expected_home: float, expected_away: float, uncertainty: float = 16.5) -> dict:
    margin = expected_home - expected_away
    draw = max(0.0, normal_cdf(3.5, margin, uncertainty) - normal_cdf(-3.5, margin, uncertainty))
    home = max(0.0, 1.0 - normal_cdf(3.5, margin, uncertainty))
    away = max(0.0, normal_cdf(-3.5, margin, uncertainty))
    total = home + draw + away
    if total <= 0:
        return {"home_win": 33.3, "draw": 33.4, "away_win": 33.3}
    hp = round(home / total * 100, 1)
    dp = round(draw / total * 100, 1)
    return {"home_win": hp, "draw": dp, "away_win": round(100 - hp - dp, 1)}


def main() -> None:
    key = os.environ.get("RUGBY_API_KEY", "").strip()
    if not key:
        raise SystemExit("Missing RUGBY_API_KEY secret")

    fixtures_payload = api_get("/fixtures", key, {"days": 60})
    competitions_payload = api_get("/competitions", key)
    rankings_payload = api_get("/rankings", key)

    fixtures = fixtures_payload.get("data", [])
    competitions = competitions_payload.get("data", [])
    rankings = rankings_payload.get("data", [])
    if not isinstance(fixtures, list):
        raise RuntimeError("Fixtures response has no data array")

    # Keep an incremental local archive of the free API's rolling results feed.
    try:
        results_payload = api_get("/results", key)
    except requests.HTTPError as exc:
        print(f"Results endpoint unavailable; retaining saved results: {exc}")
        results_payload = {"data": []}
    history_path = Path("data/results-history.json")
    try:
        history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    except (json.JSONDecodeError, OSError):
        history = []
    by_match = {m.get("id"): m for m in history if isinstance(m, dict) and m.get("id")}
    for match in results_payload.get("data", []):
        if not isinstance(match, dict) or match.get("status") != "finished":
            continue
        h, a = match.get("home") or {}, match.get("away") or {}
        if h.get("id") and a.get("id") and h.get("score") is not None and a.get("score") is not None:
            by_match[match.get("id")] = {
                "id": match.get("id"), "date": match.get("date"),
                "competition": (match.get("competition") or {}).get("name", "Rugby"),
                "home": {"id": h.get("id"), "name": h.get("name"), "score": h.get("score")},
                "away": {"id": a.get("id"), "name": a.get("name"), "score": a.get("score")},
            }
    results_history = sorted(by_match.values(), key=lambda x: (x.get("date") or "", x.get("id") or ""))[-2000:]
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(results_history, ensure_ascii=False, indent=2), encoding="utf-8")

    team_games = {}
    for result in results_history:
        h, a = result["home"], result["away"]
        hs, aws = float(h["score"]), float(a["score"])
        team_games.setdefault(h["id"], []).append({"date": result.get("date"), "opponent": a.get("name"), "venue": "H", "scored": hs, "conceded": aws, "outcome": "W" if hs > aws else ("D" if hs == aws else "L")})
        team_games.setdefault(a["id"], []).append({"date": result.get("date"), "opponent": h.get("name"), "venue": "A", "scored": aws, "conceded": hs, "outcome": "W" if aws > hs else ("D" if hs == aws else "L")})
    recent_form = {}
    for team_id, games in team_games.items():
        last = sorted(games, key=lambda x: x.get("date") or "", reverse=True)[:5]
        if last:
            recent_form[team_id] = {
                "sequence": "".join(x["outcome"] for x in last), "played": len(last),
                "points_for_avg": round(sum(x["scored"] for x in last) / len(last), 1),
                "points_against_avg": round(sum(x["conceded"] for x in last) / len(last), 1),
                "points_diff_avg": round(sum(x["scored"] - x["conceded"] for x in last) / len(last), 1),
                "results": last,
            }

    # League tables are free for the current season. Limit calls to keep
    # comfortably inside the free key's daily allowance.
    season_ids = []
    for match in fixtures:
        season = match.get("season") or {}
        season_id = season.get("id") if isinstance(season, dict) else None
        if season_id and season_id not in season_ids:
            season_ids.append(season_id)
    standings_by_season = {}
    for season_id in season_ids[:MAX_STANDINGS]:
        try:
            standings_by_season[season_id] = api_get(
                f"/seasons/{season_id}/standings", key
            ).get("data", [])
        except requests.HTTPError as exc:
            # One unavailable/unsupported league must not break the whole feed.
            print(f"Standings unavailable for {season_id}: {exc}")

    national_ratings = {}
    for item in rankings:
        team = item.get("team") or {}
        if team.get("id") is not None:
            national_ratings[team["id"]] = {
                "name": team.get("name", ""),
                "rating": item.get("rating"),
                "rank": item.get("rank"),
                "tests": item.get("tests"),
            }

    competition_types = {
        item.get("id"): item.get("type", "")
        for item in competitions if item.get("id")
    }

    standings_lookup = {}
    for season_id, rows in standings_by_season.items():
        for row in rows if isinstance(rows, list) else []:
            team = row.get("team") or {}
            team_id = team.get("id")
            played = row.get("p") or 0
            if team_id and played:
                standings_lookup[(season_id, team_id)] = {
                    "name": team.get("name", ""),
                    "played": played,
                    "points_for_avg": (row.get("pf") or 0) / played,
                    "points_against_avg": (row.get("pa") or 0) / played,
                    "points": row.get("pts") or 0,
                    "position": row.get("pos"),
                    "points_difference_avg": (row.get("pd") or 0) / played,
                }

    enriched = []
    for match in fixtures:
        home = match.get("home") or {}
        away = match.get("away") or {}
        if not home.get("id") or not away.get("id"):
            continue
        comp = match.get("competition") or {}
        season = match.get("season") or {}
        season_id = season.get("id") if isinstance(season, dict) else None
        home_stats = standings_lookup.get((season_id, home["id"]))
        away_stats = standings_lookup.get((season_id, away["id"]))
        prediction = None
        basis = None
        home_form = recent_form.get(home["id"])
        away_form = recent_form.get(away["id"])

        if home_stats and away_stats:
            h_for, h_against = home_stats["points_for_avg"], home_stats["points_against_avg"]
            a_for, a_against = away_stats["points_for_avg"], away_stats["points_against_avg"]
            if home_form and away_form:
                h_for = 0.70 * h_for + 0.30 * home_form["points_for_avg"]
                h_against = 0.70 * h_against + 0.30 * home_form["points_against_avg"]
                a_for = 0.70 * a_for + 0.30 * away_form["points_for_avg"]
                a_against = 0.70 * a_against + 0.30 * away_form["points_against_avg"]
            home_expected = max(5.0, (h_for + a_against) / 2 + 2.5)
            away_expected = max(5.0, (a_for + h_against) / 2 - 1.0)
            table_gap = (home_stats["points_difference_avg"] - away_stats["points_difference_avg"]) * 0.18
            form_gap = ((home_form["points_diff_avg"] - away_form["points_diff_avg"]) * 0.12
                        if home_form and away_form else 0.0)
            correction = max(-5.0, min(5.0, table_gap + form_gap))
            home_expected += correction / 2
            away_expected -= correction / 2
            prediction = {
                **match_probabilities(home_expected, away_expected),
                "home_score": round(home_expected), "away_score": round(away_expected),
                "confidence": "wstępna",
            }
            basis = "tabela + średnie punktowe" + (" + forma (ostatnie 5)" if home_form and away_form else "")
        elif home_form and away_form:
            home_expected = max(5.0, (home_form["points_for_avg"] + away_form["points_against_avg"]) / 2 + 2.5)
            away_expected = max(5.0, (away_form["points_for_avg"] + home_form["points_against_avg"]) / 2 - 1.0)
            prediction = {
                **match_probabilities(home_expected, away_expected, uncertainty=19.0),
                "home_score": round(home_expected), "away_score": round(away_expected),
                "confidence": "niska",
            }
            basis = "forma z ostatnich 5 meczów"
        else:
            h_rank = national_ratings.get(home["id"])
            a_rank = national_ratings.get(away["id"])
            comp_type = competition_types.get(comp.get("id"), "")
            if h_rank and a_rank and comp_type == "international":
                rating_gap = float(h_rank.get("rating") or 0) - float(a_rank.get("rating") or 0)
                expected_margin = max(-35.0, min(35.0, rating_gap * 0.75 + 3.0))
                prediction = {
                    **match_probabilities(30.0 + expected_margin / 2, 30.0 - expected_margin / 2),
                    "home_score": None, "away_score": None, "confidence": "wstępna",
                }
                basis = "ranking reprezentacji + przewaga gospodarzy"

        enriched.append({
            "id": match.get("id"),
            "date": match.get("date"),
            "kickoff_utc": match.get("kickoff_utc"),
            "status": match.get("status"),
            "competition": comp.get("name", "Rugby"),
            "competition_type": competition_types.get(comp.get("id"), ""),
            "season": season.get("name") if isinstance(season, dict) else season,
            "home": {"id": home.get("id"), "name": home.get("name")},
            "away": {"id": away.get("id"), "name": away.get("name")},
            "prediction": prediction,
            "prediction_basis": basis,
            "home_form": home_form,
            "away_form": away_form,
        })

    # Preserve the first forecast made for each fixture, then score it when
    # the result arrives. This creates a genuine prospective validation set.
    prediction_path = Path("data/prediction-history.json")
    try:
        prediction_ledger = json.loads(prediction_path.read_text(encoding="utf-8")) if prediction_path.exists() else []
    except (json.JSONDecodeError, OSError):
        prediction_ledger = []
    ledger_by_id = {x.get("id"): x for x in prediction_ledger if isinstance(x, dict) and x.get("id")}
    for result in results_history:
        saved = ledger_by_id.get(result.get("id"))
        if saved and saved.get("actual") is None:
            hs, aws = float(result["home"]["score"]), float(result["away"]["score"])
            actual = "home" if hs > aws else ("away" if aws > hs else "draw")
            predicted = max(("home", "draw", "away"), key=lambda k: saved["probabilities"][k])
            target = {"home": 1.0, "draw": 1.0, "away": 1.0}
            for key in target:
                target[key] = 1.0 if key == actual else 0.0
            brier = sum((saved["probabilities"][key] - target[key]) ** 2 for key in target) / 3
            saved.update({"actual": actual, "actual_score": [hs, aws], "hit": predicted == actual, "brier": round(brier, 5)})
    for match in enriched:
        pred = match.get("prediction")
        if pred and match.get("status") == "scheduled" and match.get("id") not in ledger_by_id:
            ledger_by_id[match["id"]] = {
                "id": match["id"], "date": match.get("date"), "competition": match.get("competition"),
                "home": match["home"].get("name"), "away": match["away"].get("name"),
                "probabilities": {"home": pred["home_win"] / 100, "draw": pred["draw"] / 100, "away": pred["away_win"] / 100},
                "prediction_basis": match.get("prediction_basis"), "actual": None,
            }
    prediction_ledger = sorted(ledger_by_id.values(), key=lambda x: (x.get("date") or "", x.get("id") or ""))[-5000:]
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    prediction_path.write_text(json.dumps(prediction_ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    settled = [x for x in prediction_ledger if x.get("actual") is not None]
    validation = {
        "settled_predictions": len(settled),
        "hit_rate": round(sum(1 for x in settled if x.get("hit")) / len(settled) * 100, 1) if settled else None,
        "brier_score": round(sum(x["brier"] for x in settled) / len(settled), 4) if settled else None,
    }

    enriched.sort(key=lambda item: (item.get("kickoff_utc") or item.get("date") or "", item["id"] or ""))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "rugbyAPI",
        "window_days": 60,
        "fixtures_count": len(enriched),
        "competitions_count": len(competitions),
        "standings_loaded": len(standings_by_season),
        "results_fetched": len(results_payload.get("data", [])),
        "results_history_count": len(results_history),
        "teams_with_form": len(recent_form),
        "validation": validation,
        "rankings_as_of": rankings_payload.get("as_of"),
        "fixtures": enriched,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Saved {len(enriched)} fixtures; standings: {len(standings_by_season)}; "
        f"national rankings as of {payload['rankings_as_of']}"
    )


if __name__ == "__main__":
    main()
