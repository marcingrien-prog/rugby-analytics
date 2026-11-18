from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .model import Team, simulate_match

app = FastAPI(title="Rugby Analytics API", version="0.1.0", description="Experimental rugby union match prediction API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Initial demonstration priors only. Replace with ratings and per-match rates
# computed from a verified historical match database before production use.
TEAMS = {
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

@app.get("/health")
def health(): return {"status":"ok","version":"0.1.0","data_status":"demo_priors_only"}

@app.get("/teams")
def teams():
    return [{"id":k,"name":v.name,"elo":v.elo,"tries_for":v.tries_for,"tries_against":v.tries_against,"data_status":"demo_prior"} for k,v in TEAMS.items()]

@app.post("/predict")
def predict(req: PredictionRequest):
    if req.team_a not in TEAMS or req.team_b not in TEAMS: raise HTTPException(404,"Unknown team id")
    if req.team_a == req.team_b: raise HTTPException(400,"Choose two different teams")
    advantage = 55 if req.venue == "a_home" else -55 if req.venue == "b_home" else 0
    return simulate_match(TEAMS[req.team_a],TEAMS[req.team_b],req.simulations,advantage,req.seed)
