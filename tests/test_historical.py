from backend.historical import build_ratings, head_to_head


def sample_matches():
    return [
        {"match_id":"1","date":__import__("datetime").date(2024,1,1),"home_raw":"new-zealand","away_raw":"ireland","home_score":24,"away_score":17,"competition":"Test","confidence":"high"},
        {"match_id":"2","date":__import__("datetime").date(2024,2,1),"home_raw":"ireland","away_raw":"new-zealand","home_score":20,"away_score":25,"competition":"Test","confidence":"high"},
        {"match_id":"3","date":__import__("datetime").date(2024,3,1),"home_raw":"france","away_raw":"ireland","home_score":30,"away_score":24,"competition":"Test","confidence":"high"},
    ]


def test_ratings_and_recent_form_are_built_chronologically():
    profiles, meta = build_ratings(sample_matches())
    assert meta["matches_used"] == 3
    assert profiles["NZL"]["matches"] == 2
    assert profiles["NZL"]["wins"] == 2
    assert profiles["IRE"]["last10"]["losses"] == 3
    assert profiles["NZL"]["elo"] > 1500


def test_head_to_head_is_oriented_to_requested_team_order():
    result = head_to_head(sample_matches(), "ireland", "new-zealand")
    assert result["matches"] == 2
    assert result["wins_a"] == 0
    assert result["wins_b"] == 2
