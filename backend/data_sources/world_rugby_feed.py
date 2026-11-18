"""Client for TheBreakdown's public international Test match JSON feed.

The feed identifies its underlying source as the World Rugby match feed.
Check the provider's current terms before redistributing downloaded data.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import requests

BASE_URL = "https://thebreakdown.zone/api/matches"
SOURCE_NAME = "TheBreakdown / World Rugby Test match feed"


class FeedError(RuntimeError):
    """Raised when the upstream feed cannot be read or parsed."""


def fetch_completed_tests(
    start_year: int | None = None,
    end_year: int | None = None,
    page_size: int = 100,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """Download completed men's Test matches, following all result pages."""
    if not 1 <= page_size <= 250:
        raise ValueError("page_size must be between 1 and 250")

    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "User-Agent": "RugbyAnalytics/0.2 (+https://github.com/marcingrien-prog/rugby-analytics)",
    })

    first = _get_page(session, 1, page_size, timeout)
    pages = int(first.get("pages", 1) or 1)
    rows: list[dict[str, Any]] = list(first.get("rows", []))

    for page in range(2, pages + 1):
        payload = _get_page(session, page, page_size, timeout)
        rows.extend(payload.get("rows", []))

    normalized: list[dict[str, Any]] = []
    for row in rows:
        match = normalize_match(row)
        if match is None:
            continue
        year = int(match["date"][:4])
        if start_year is not None and year < start_year:
            continue
        if end_year is not None and year > end_year:
            continue
        normalized.append(match)

    normalized.sort(key=lambda item: (item["date"], item["match_id"]))
    return normalized


def _get_page(session: requests.Session, page: int, page_size: int, timeout: int) -> dict[str, Any]:
    params = {
        "scope": "tests",
        "status": "completed",
        "sort": "date",
        "page": page,
        "pageSize": page_size,
    }
    try:
        response = session.get(BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise FeedError(f"Could not retrieve results page {page}: {exc}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise FeedError(f"Unexpected response structure on page {page}")
    return payload


def normalize_match(row: dict[str, Any]) -> dict[str, Any] | None:
    """Map upstream field names to the app's stable match schema."""
    try:
        match_date = date.fromisoformat(str(row["date"])).isoformat()
        score_a = int(row["scoreA"])
        score_b = int(row["scoreB"])
        team_a = str(row["teamA"]).strip().lower()
        team_b = str(row["teamB"]).strip().lower()
        match_id = str(row["id"]).strip()
    except (KeyError, TypeError, ValueError):
        # Historical entries with no score/date are deliberately excluded.
        return None

    if not all((match_id, team_a, team_b)) or score_a < 0 or score_b < 0:
        return None

    return {
        "match_id": match_id,
        "date": match_date,
        "home_team": team_a,
        "away_team": team_b,
        "home_score": score_a,
        "away_score": score_b,
        "competition": str(row.get("competition") or ""),
        "venue": str(row.get("venue") or ""),
        "city": str(row.get("city") or ""),
        "country": str(row.get("country") or ""),
        "neutral": "",
        "confidence": str(row.get("confidence") or "unknown"),
        "source": SOURCE_NAME,
    }
