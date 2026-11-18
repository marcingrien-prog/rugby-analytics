"""Build team ratings and form metrics from the imported match CSV.

Only final scores are used. Try counts, lineups, venue advantage and detailed
scoring events are not inferred from points totals.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "international_results.csv"
INITIAL_ELO = 1500.0
ELO_K = 20.0

ALIASES = {
    "new-zealand": ("NZL", "Nowa Zelandia"),
    "new_zealand": ("NZL", "Nowa Zelandia"),
    "new zealand": ("NZL", "Nowa Zelandia"),
    "all-blacks": ("NZL", "Nowa Zelandia"),
    "south-africa": ("RSA", "RPA"),
    "south africa": ("RSA", "RPA"),
    "springboks": ("RSA", "RPA"),
    "ireland": ("IRE", "Irlandia"),
    "france": ("FRA", "Francja"),
    "england": ("ENG", "Anglia"),
    "scotland": ("SCO", "Szkocja"),
    "argentina": ("ARG", "Argentyna"),
    "australia": ("AUS", "Australia"),
    "wales": ("WAL", "Walia"),
    "italy": ("ITA", "Włochy"),
    "japan": ("JPN", "Japonia"),
    "fiji": ("FIJ", "Fidżi"),
    "samoa": ("SAM", "Samoa"),
    "tonga": ("TGA", "Tonga"),
    "georgia": ("GEO", "Gruzja"),
    "uruguay": ("URU", "Urugwaj"),
    "portugal": ("POR", "Portugalia"),
    "romania": ("ROU", "Rumunia"),
    "united-states": ("USA", "USA"),
    "usa": ("USA", "USA"),
    "canada": ("CAN", "Kanada"),
    "spain": ("ESP", "Hiszpania"),
    "namibia": ("NAM", "Namibia"),
    "chile": ("CHI", "Chile"),
    "russia": ("RUS", "Rosja"),
    "russian-federation": ("RUS", "Rosja"),
    "hong-kong": ("HKG", "Hongkong"),
    "hongkong": ("HKG", "Hongkong"),
    "zimbabwe": ("ZIM", "Zimbabwe"),
    "ivory-coast": ("CIV", "Wybrzeże Kości Słoniowej"),
    "cote-divoire": ("CIV", "Wybrzeże Kości Słoniowej"),
    "kenya": ("KEN", "Kenia"),
    "brazil": ("BRA", "Brazylia"),
    "paraguay": ("PAR", "Paragwaj"),
    "netherlands": ("NED", "Holandia"),
    "belgium": ("BEL", "Belgia"),
    "germany": ("GER", "Niemcy"),
    "switzerland": ("SUI", "Szwajcaria"),
    "poland": ("POL", "Polska"),
}


def _team_identity(raw: str) -> tuple[str, str]:
    key = re.sub(r"\s+", " ", raw.strip().lower())
    if key in ALIASES:
        return ALIASES[key]
    slug = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
    code = (re.sub(r"[^A-Z]", "", raw.upper())[:3] or "UNK")
    name = raw.replace("-", " ").replace("_", " ").title()
    return code, name


def load_matches(path: Path = DATA_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    matches: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            try:
                match = {
                    "match_id": row["match_id"],
                    "date": date.fromisoformat(row["date"]),
                    "home_raw": row["home_team"],
                    "away_raw": row["away_team"],
                    "home_score": int(row["home_score"]),
                    "away_score": int(row["away_score"]),
                    "competition": row.get("competition", ""),
                    "confidence": row.get("confidence", "unknown"),
                }
            except (KeyError, TypeError, ValueError):
                continue
            if match["home_raw"] == match["away_raw"]:
                continue
            matches.append(match)
    return sorted(matches, key=lambda item: (item["date"], item["match_id"]))


def build_ratings(matches: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    ratings: dict[str, float] = defaultdict(lambda: INITIAL_ELO)
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    h2h: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    used = 0

    for match in matches:
        a_id, a_name = _team_identity(match["home_raw"])
        b_id, b_name = _team_identity(match["away_raw"])
        if a_id == b_id:
            continue
        a_score, b_score = match["home_score"], match["away_score"]
        ra, rb = ratings[a_id], ratings[b_id]
        expected_a = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
        actual_a = 1.0 if a_score > b_score else 0.5 if a_score == b_score else 0.0
        delta = ELO_K * (actual_a - expected_a)
        ratings[a_id] = ra + delta
        ratings[b_id] = rb - delta

        common = {
            "date": match["date"].isoformat(),
            "competition": match["competition"],
            "confidence": match["confidence"],
        }
        records[a_id].append({**common, "team_id": a_id, "team_name": a_name,
                              "opponent_id": b_id, "opponent": b_name,
                              "points_for": a_score, "points_against": b_score,
                              "result": "W" if a_score > b_score else "D" if a_score == b_score else "L"})
        records[b_id].append({**common, "team_id": b_id, "team_name": b_name,
                              "opponent_id": a_id, "opponent": a_name,
                              "points_for": b_score, "points_against": a_score,
                              "result": "W" if b_score > a_score else "D" if a_score == b_score else "L"})
        key = tuple(sorted((a_id, b_id)))
        h2h[key].append({"date": common["date"], "team_a": a_id, "team_b": b_id,
                         "score_a": a_score, "score_b": b_score})
        used += 1

    profiles: dict[str, dict[str, Any]] = {}
    for team_id, games in records.items():
        last = games[-10:]
        all_pf = [g["points_for"] for g in games]
        all_pa = [g["points_against"] for g in games]
        wins = sum(g["result"] == "W" for g in games)
        draws = sum(g["result"] == "D" for g in games)
        profiles[team_id] = {
            "id": team_id,
            "name": games[-1]["team_name"],
            "elo": round(ratings[team_id], 1),
            "matches": len(games),
            "wins": wins, "draws": draws, "losses": len(games) - wins - draws,
            "points_for_avg": round(mean(all_pf), 2),
            "points_against_avg": round(mean(all_pa), 2),
            "points_difference_avg": round(mean([x-y for x, y in zip(all_pf, all_pa)]), 2),
            "last10": {
                "matches": len(last),
                "wins": sum(g["result"] == "W" for g in last),
                "draws": sum(g["result"] == "D" for g in last),
                "losses": sum(g["result"] == "L" for g in last),
                "points_for_avg": round(mean(g["points_for"] for g in last), 2),
                "points_against_avg": round(mean(g["points_against"] for g in last), 2),
                "results": "".join(g["result"] for g in last),
            },
            "recent_matches": list(reversed(games[-10:])),
            "score_sd": round(pstdev(all_pf), 2) if len(all_pf) > 1 else 10.0,
            "data_status": "historical_csv",
        }

    meta = {
        "matches_used": used,
        "teams": len(profiles),
        "first_match": matches[0]["date"].isoformat() if matches else None,
        "last_match": matches[-1]["date"].isoformat() if matches else None,
        "elo_initial": INITIAL_ELO,
        "elo_k": ELO_K,
        "venue_adjustment": "not_applied; source neutral/home flag is not reliable enough yet",
        "source_confidence": "retained per match; not yet filtered or weighted",
    }
    return profiles, {"status": "historical_csv" if used else "no_historical_data", **meta}


def head_to_head(matches: list[dict[str, Any]], team_a: str, team_b: str) -> dict[str, Any]:
    a, _ = _team_identity(team_a)
    b, _ = _team_identity(team_b)
    relevant = []
    for match in matches:
        x, _ = _team_identity(match["home_raw"])
        y, _ = _team_identity(match["away_raw"])
        if {x, y} != {a, b}:
            continue
        score_a = match["home_score"] if x == a else match["away_score"]
        score_b = match["away_score"] if x == a else match["home_score"]
        relevant.append({"date": match["date"].isoformat(), "score_a": score_a,
                         "score_b": score_b, "competition": match["competition"]})
    return {"matches": len(relevant), "wins_a": sum(x["score_a"] > x["score_b"] for x in relevant),
            "draws": sum(x["score_a"] == x["score_b"] for x in relevant),
            "wins_b": sum(x["score_a"] < x["score_b"] for x in relevant),
            "recent": list(reversed(relevant[-10:]))}
