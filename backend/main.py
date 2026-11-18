from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .model import Team, simulate_match, simulate_from_historical_points
from .historical import DATA_PATH, build_ratings, head_to_head, load_matches

app = FastAPI(title="Rugby Analytics API", version="0.2.0", description="Experimental rugby union match prediction API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Fallbacks are explicitly marked as demo priors and used only until a CSV exists.
DEMO_TEAMS = {
 "NZL": Team("Nowa Zelandia",1885,2.9,2.0,1.0,1.0),
 "RSA": Team("RPA",1900,2.9,1.9,1.1,.9),
 "IRE": Team("Irlandia",1860,2.7,1.8,1.0,.9),
 "FRA": Team("Francja",1850,2.8,2.1,1.0,1.0),
 "ENG": Team("Anglia",1810,2.5,2.0,1.0,1.0),
 "SCO": Team("Szkocja",1760,2.6,2.3,1.0,1.1),
 "ARG": Team("Argentyna",1750,2.4,2.1,1.0,1.0),
 "AUS": Team("Australia",1725,2.5,2.5,1.0,1.1),
 "WAL": Team("Walia",1700,2.2,2.4,.9,1.1),
 "ITA": Team("Włochy",1650,2.3,2.7,.9,1.2),
 "JPN": Team("Japonia",1640,2.5,2.8,.9,1.2),
 "FIJ": Team("Fidżi",1690,2.7,2.8,1.0,1.2),
}

class PredictionRequest(BaseModel):
    team_a: str
    team_b: str
    venue: str = Field(default="neutral", pattern="^(neutral|a_home|b_home)$")
    simulations: int = Field(default=20000, ge=100, le=500000)
    seed: int | None = None


def current_data():
    matches = load_matches()
    profiles, meta = build_ratings(matches)
    return matches, profiles, meta


@app.get("/health")
def health():
    _, _, meta = current_data()
    return {"status":"ok","version":"0.2.0","data_status":meta["status"],"matches_used":meta["matches_used"]}


@app.get("/analytics/status")
def analytics_status():
    _, profiles, meta = current_data()
    return {**meta, "csv_path": str(DATA_PATH), "csv_exists": DATA_PATH.exists(),
            "teams_available": len(profiles)}


@app.get("/teams")
def teams():
    _, profiles, _ = current_data()
    if profiles:
        return [{"id":k,"name":v["name"],"elo":v["elo"],"matches":v["matches"],
                 "points_for_avg":v["points_for_avg"],"points_against_avg":v["points_against_avg"],
                 "last10":v["last10"],"data_status":"historical_csv"} for k,v in sorted(profiles.items(), key=lambda x:x[1]["elo"], reverse=True)]
    return [{"id":k,"name":v.name,"elo":v.elo,"tries_for":v.tries_for,
             "tries_against":v.tries_against,"data_status":"demo_prior"} for k,v in DEMO_TEAMS.items()]


@app.get("/analytics/teams/{team_id}")
def team_analytics(team_id: str):
    _, profiles, meta = current_data()
    if team_id not in profiles:
        raise HTTPException(404, "No historical profile for this team. Import the results CSV first.")
    profile = profiles[team_id]
    return {**profile, "dataset": meta}


@app.get("/analytics/head-to-head/{team_a}/{team_b}")
def analytics_head_to_head(team_a: str, team_b: str):
    matches, profiles, _ = current_data()
    if not matches:
        raise HTTPException(404, "Historical results CSV is not available.")
    return head_to_head(matches, team_a, team_b)


@app.post("/predict")
def predict(req: PredictionRequest):
    if req.team_a == req.team_b:
        raise HTTPException(400,"Choose two different teams")
    advantage = 3.0 if req.venue == "a_home" else -3.0 if req.venue == "b_home" else 0.0
    _, profiles, meta = current_data()
    if profiles:
        if req.team_a not in profiles or req.team_b not in profiles:
            raise HTTPException(404, "One or both teams are missing from imported historical data.")
        return simulate_from_historical_points(profiles[req.team_a], profiles[req.team_b],
                                               req.simulations, advantage, req.seed)
    if req.team_a not in DEMO_TEAMS or req.team_b not in DEMO_TEAMS:
        raise HTTPException(404,"Unknown team id")
    result = simulate_match(DEMO_TEAMS[req.team_a],DEMO_TEAMS[req.team_b],
                            req.simulations, 55 if req.venue == "a_home" else -55 if req.venue == "b_home" else 0,
                            req.seed)
    result["data_status"] = meta["status"]
    return result
