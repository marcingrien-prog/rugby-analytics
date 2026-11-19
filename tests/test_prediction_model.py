from scripts.fetch_live_data import match_probabilities


def test_match_probabilities_sum_to_100():
    result = match_probabilities(31, 27)
    assert round(result["home_win"] + result["draw"] + result["away_win"], 1) == 100.0


def test_stronger_expected_home_score_increases_home_probability():
    balanced = match_probabilities(28, 28)
    home_favourite = match_probabilities(38, 20)
    assert home_favourite["home_win"] > balanced["home_win"]
    assert home_favourite["away_win"] < balanced["away_win"]


def test_probabilities_are_bounded():
    for home, away in [(10, 70), (70, 10), (30, 30), (0, 0)]:
        result = match_probabilities(home, away)
        assert all(0 <= value <= 100 for value in result.values())
        assert round(sum(result.values()), 1) == 100.0
