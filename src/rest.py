"""Absences, and the difference between the two kinds the data cannot tell apart.

Gregg Popovich did not invent resting players, but he is the reason the league
has a rule about it. The natural question - what did it buy? - runs immediately
into the fact that **the public box score does not record why a player did not
play**. There is a flag for "did not play" and there is the absence of a row
altogether, and neither says injury, rest, suspension or newborn child.

So the project does not pretend to observe rest. It observes *absences*, splits
them by shape, and then checks whether the split behaves the way rest should.

An absence that lasts one or two games with games played on either side is the
shape a planned night off makes. A torn ligament does not make that shape. That
is the whole inference, it is stated as such throughout, and the test of it is
whether isolated absences line up with the things a coach would schedule around
- the second night of a back-to-back, a heavy week - while long absences do not.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FRANCHISES = {
    "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GS",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NJ", "NO",
    "NY", "OKC", "ORL", "PHI", "PHX", "POR", "SA", "SAC", "SEA", "TOR",
    "UTAH", "WSH",
}


def team_schedule(box: pd.DataFrame) -> pd.DataFrame:
    """One row per team-game: date, opponent, result, and how they arrived."""
    g = (box.groupby(["season", "team", "game_id"], observed=True)
         .agg(date=("date", "first"), opponent=("opponent", "first"),
              team_score=("team_score", "first"),
              opp_score=("opponent_team_score", "first"),
              home=("home", "first"))
         .reset_index()
         .sort_values(["season", "team", "date"]))
    g["margin"] = g["team_score"] - g["opp_score"]
    by = g.groupby(["season", "team"], sort=False)
    prev = by["date"].shift(1)
    g["rest"] = (g["date"] - prev).dt.days - 1
    g["b2b"] = (g["rest"] == 0).astype(int)
    g["rest"] = g["rest"].fillna(3).clip(0, 3)
    g["game_no"] = by.cumcount() + 1

    dens = []
    for _, sub in g.groupby(["season", "team"], sort=False):
        s = sub.set_index("date")["game_no"]
        dens.append(s.rolling("7D").count().to_numpy())
    g["games_7d"] = np.concatenate(dens)
    return g.reset_index(drop=True)


def opponent_strength(sched: pd.DataFrame) -> pd.DataFrame:
    """Each team-season's average margin, attached to its opponents' games.

    Used as a control, so the question "did they sit people against bad teams"
    can be answered rather than assumed.
    """
    season_margin = (sched.groupby(["season", "team"], observed=True)["margin"]
                     .mean().rename("team_margin").reset_index())
    out = sched.merge(season_margin, on=["season", "team"], how="left")
    out = out.merge(season_margin.rename(columns={"team": "opponent",
                                                  "team_margin": "opp_margin"}),
                    on=["season", "opponent"], how="left")
    return out


def rotation(box: pd.DataFrame, min_games: int, min_mpg: float) -> pd.DataFrame:
    """Players who were a real part of a team's season."""
    played = box[box["played"] == 1]
    agg = (played.groupby(["season", "team", "athlete_id", "player"], observed=True)
           .agg(games=("minutes", "size"), mpg=("minutes", "mean"),
                total_minutes=("minutes", "sum"))
           .reset_index())
    return agg[(agg["games"] >= min_games) & (agg["mpg"] >= min_mpg)]


def attendance(sched: pd.DataFrame, box: pd.DataFrame,
               roster: pd.DataFrame) -> pd.DataFrame:
    """Every rotation player crossed with every game their team played.

    A player is `played` when the box score gives them minutes, and `missed`
    otherwise - whether they were listed as a did-not-play or do not appear in
    the file at all. The two are kept as separate columns because they mean
    slightly different things (dressed and unused, against not dressed) and
    because the mix between them changes over the sample.
    """
    keys = roster[["season", "team", "athlete_id", "player"]]
    grid = sched.merge(keys, on=["season", "team"], how="inner")
    seen = box[["season", "team", "game_id", "athlete_id", "played", "dnp",
                "minutes", "plus_minus", "points", "starter"]]
    out = grid.merge(seen, on=["season", "team", "game_id", "athlete_id"],
                     how="left")
    out["played"] = out["played"].fillna(0).astype(int)
    out["dnp"] = out["dnp"].fillna(0).astype(int)
    out["absent"] = ((out["played"] == 0) & (out["dnp"] == 0)).astype(int)
    out["missed"] = 1 - out["played"]
    return out.sort_values(["season", "team", "athlete_id", "date"])


def absence_runs(att: pd.DataFrame, max_isolated: int) -> pd.DataFrame:
    """Label each missed game with the length of the run of misses it sits in.

    A run bounded by played games on both sides, inside one season, and no
    longer than `max_isolated`, is what this project calls a planned absence.
    Everything else is left unlabelled rather than called an injury, because it
    is not one and the data does not say.
    """
    out = att.copy()
    out["run_len"] = 0
    out["isolated"] = 0
    for _, block in out.groupby(["season", "team", "athlete_id"], sort=False):
        missed = block["missed"].to_numpy()
        idx = block.index.to_numpy()
        i = 0
        n = len(missed)
        while i < n:
            if missed[i] == 0:
                i += 1
                continue
            j = i
            while j < n and missed[j] == 1:
                j += 1
            run = j - i
            bounded = i > 0 and j < n          # played before and after, same season
            out.loc[idx[i:j], "run_len"] = run
            if bounded and run <= max_isolated:
                out.loc[idx[i:j], "isolated"] = 1
            i = j
    return out
