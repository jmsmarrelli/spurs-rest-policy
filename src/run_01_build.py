"""Stage 1 - twenty seasons of player box scores into an attendance panel.

    python src/run_01_build.py

For every rotation player and every game their team played: did they play, and
if not, what shape was the absence. Also builds each team's schedule with rest,
density and opponent strength attached, since the question of *when* teams sat
people needs all three.

Writes data/processed/attendance.csv.gz, data/processed/schedule.csv.gz,
data/processed/playoffs.csv.gz and output/coverage.csv.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (MAX_ISOLATED_RUN, MIN_GAMES_PLAYED, MIN_MINUTES_PER_GAME,  # noqa: E402
                    OUT, PROC, RAW, SEASONS)
import rest as R  # noqa: E402

COLS = ["game_id", "season", "season_type", "game_date", "athlete_id",
        "athlete_display_name", "team_abbreviation", "opponent_team_abbreviation",
        "minutes", "plus_minus", "points", "starter", "did_not_play",
        "home_away", "team_score", "opponent_team_score"]

REGULAR = 2
POSTSEASON = 3


def playoff_games(raw: pd.DataFrame, season: int) -> pd.DataFrame:
    """One row per postseason team-game, for the April question."""
    p = raw[raw["season_type"] == POSTSEASON]
    p = p[p["team_abbreviation"].isin(R.FRANCHISES)
          & p["opponent_team_abbreviation"].isin(R.FRANCHISES)]
    if p.empty:
        return pd.DataFrame()
    g = (p.groupby(["team_abbreviation", "game_id"], observed=True)
         .agg(opponent=("opponent_team_abbreviation", "first"),
              team_score=("team_score", "first"),
              opp_score=("opponent_team_score", "first"),
              home_away=("home_away", "first"))
         .reset_index()
         .rename(columns={"team_abbreviation": "team"}))
    g["season"] = season
    g["margin"] = g["team_score"] - g["opp_score"]
    g["home"] = (g["home_away"] == "home").astype(int)
    return g[["season", "team", "game_id", "opponent", "margin", "home"]]


def load_season(season: int) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    path = RAW / "player_box" / f"player_box_{season}.csv.gz"
    if not path.exists():
        raise SystemExit(f"missing {path}. See data/README.md.")
    raw = pd.read_csv(path, usecols=COLS, low_memory=False)
    playoffs = playoff_games(raw, season)
    b = raw[raw["season_type"] == REGULAR]
    b = b[b["athlete_id"].notna()]

    exhibition = int((~b["team_abbreviation"].isin(R.FRANCHISES)).sum())
    b = b[b["team_abbreviation"].isin(R.FRANCHISES)
          & b["opponent_team_abbreviation"].isin(R.FRANCHISES)]

    b = b.rename(columns={"athlete_display_name": "player",
                          "team_abbreviation": "team",
                          "opponent_team_abbreviation": "opponent"})
    b["date"] = pd.to_datetime(b["game_date"])
    b["athlete_id"] = b["athlete_id"].astype("int64")
    b["home"] = (b["home_away"] == "home").astype(int)
    b["minutes"] = pd.to_numeric(b["minutes"], errors="coerce")
    b["played"] = (b["minutes"].fillna(0) > 0).astype(int)
    b["dnp"] = ((b["played"] == 0)
                & b["did_not_play"].fillna(False).astype(bool)).astype(int)
    audit = {"season": season, "rows": len(b), "dropped_exhibition": exhibition,
             "playoff_games": int(playoffs["game_id"].nunique()) if len(playoffs) else 0}
    return b, audit, playoffs


def main() -> None:
    frames, audit, post = [], [], []
    for season in SEASONS:
        b, a, p = load_season(season)
        frames.append(b)
        audit.append(a)
        if len(p):
            post.append(p)
        print(f"  {season}: {b['game_id'].nunique():,} games, {len(b):,} player-game rows",
              flush=True)
    box = pd.concat(frames, ignore_index=True)

    playoffs = pd.concat(post, ignore_index=True)
    playoffs.to_csv(PROC / "playoffs.csv.gz", index=False, compression="gzip")

    sched = R.opponent_strength(R.team_schedule(box))
    sched.to_csv(PROC / "schedule.csv.gz", index=False, compression="gzip")

    roster = R.rotation(box, MIN_GAMES_PLAYED, MIN_MINUTES_PER_GAME)
    att = R.attendance(sched, box, roster)
    att = R.absence_runs(att, MAX_ISOLATED_RUN)
    att.to_csv(PROC / "attendance.csv.gz", index=False, compression="gzip")

    cov = (att.groupby("season")
           .agg(teams=("team", "nunique"),
                rotation_players=("athlete_id", "nunique"),
                player_games=("played", "size"),
                played=("played", "sum"),
                missed=("missed", "sum"),
                isolated=("isolated", "sum"))
           .reset_index())
    cov["miss_rate"] = cov["missed"] / cov["player_games"]
    cov["isolated_rate"] = cov["isolated"] / cov["player_games"]
    cov = cov.merge(pd.DataFrame(audit), on="season")
    cov.round(5).to_csv(OUT / "coverage.csv", index=False)

    print(f"\n{len(box):,} player-game rows, {sched['game_id'].nunique():,} games")
    print(f"{playoffs['game_id'].nunique():,} postseason games, "
          f"{playoffs['season'].nunique()} postseasons")
    print(f"{len(roster):,} rotation player-seasons "
          f"({MIN_GAMES_PLAYED}+ games at {MIN_MINUTES_PER_GAME:.0f}+ minutes)")
    print(f"{len(att):,} rows in the attendance panel")
    print()
    print(cov.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
