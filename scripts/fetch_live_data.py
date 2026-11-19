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
MAX_STANDINGS = 14


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
    results_payload = api_get("/results", key)
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
            home_expected = (home_stats["points_for_avg"] + away_stats["points_against_avg"]) / 2 + 3.0
            away_expected = (away_stats["points_for_avg"] + home_stats["points_against_avg"]) / 2
            # Score-margin proxy combines attack/defence and table strength.
            table_gap = (
                (home_stats["points_difference_avg"] - away_stats["points_difference_avg"]) * 0.35
                + (home_stats["points"] - away_stats["points"]) / max(1, home_stats["played"] + away_stats["played"]) * 0.20
            )
            form_gap = (home_form["points_diff_avg"] - away_form["points_diff_avg"]) * 0.20 if home_form and away_form else 0.0
            strength_gap = table_gap + form_gap + 3.0
            p_home = logistic(strength_gap / 7.5)
            prediction = {
                "home_win": round(p_home * 100, 1),
                "draw": round(max(2.0, 7.0 - abs(strength_gap) * 0.35), 1),
                "away_win": round((1 - p_home) * 100, 1),
                "home_score": round(home_expected),
                "away_score": round(away_expected),
                "confidence": "wstępna",
            }
            # Normalize win/draw percentages to exactly 100.
            draw = prediction["draw"]
            remaining = 100 - draw
            total = prediction["home_win"] + prediction["away_win"]
            prediction["home_win"] = round(remaining * prediction["home_win"] / total, 1)
            prediction["away_win"] = round(100 - draw - prediction["home_win"], 1)
            basis = "tabela sezonu" + (" + forma z ostatnich 5 meczów" if home_form and away_form else "")
        elif home_form and away_form:
            form_gap = (home_form["points_diff_avg"] - away_form["points_diff_avg"]) * 0.22 + 3.0
            p_home = logistic(form_gap / 8.5)
            home_expected = (home_form["points_for_avg"] + away_form["points_against_avg"]) / 2 + 2.5
            away_expected = (away_form["points_for_avg"] + home_form["points_against_avg"]) / 2
            draw = 5.0
            prediction = {"home_win": round((100-draw)*p_home, 1), "draw": draw, "away_win": round(100-draw-(100-draw)*p_home, 1), "home_score": round(home_expected), "away_score": round(away_expected), "confidence": "niska"}
            basis = "forma z ostatnich 5 meczów"
        else:
            h_rank = national_ratings.get(home["id"])
            a_rank = national_ratings.get(away["id"])
            comp_type = competition_types.get(comp.get("id"), "")
            if h_rank and a_rank and comp_type == "international":
                gap = float(h_rank.get("rating") or 0) - float(a_rank.get("rating") or 0) + 3.0
                p_home = logistic(gap / 7.5)
                prediction = {
                    "home_win": round(p_home * 98, 1),
                    "draw": 2.0,
                    "away_win": round((1 - p_home) * 98, 1),
                    "home_score": None,
                    "away_score": None,
                    "confidence": "wstępna",
                }
                basis = "ranking obliczony na podstawie testów"

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
