#!/usr/bin/env python3
"""Import completed international rugby union Test results into CSV."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from backend.data_sources.world_rugby_feed import fetch_completed_tests

FIELDS = [
    "match_id", "date", "home_team", "away_team", "home_score", "away_score",
    "competition", "venue", "city", "country", "neutral", "confidence", "source",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, help="Keep matches from this year onward")
    parser.add_argument("--end-year", type=int, help="Keep matches through this year")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--output", default="data/international_results.csv")
    args = parser.parse_args()

    matches = fetch_completed_tests(
        start_year=args.start_year,
        end_year=args.end_year,
        page_size=args.page_size,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(matches)

    print(f"Imported {len(matches)} matches into {output}")
    if matches:
        print(f"Date range: {matches[0]['date']} – {matches[-1]['date']}")
        print("Check confidence/source fields before using the data for model training.")


if __name__ == "__main__":
    main()
