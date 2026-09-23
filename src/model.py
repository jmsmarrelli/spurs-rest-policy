"""A margin model, so "what did it cost" has something to be measured against.

One row per game from the home team's side. The outcome is the final margin.

    margin  =  strength(home team, that season)
             - strength(away team, that season)
             + home advantage for that season
             + the schedule burdens each side arrived with
             + error

Team-season effects absorb every reason one team beats another that has nothing
to do with the calendar or the roster on the night. What is left over is what a
game was worth relative to expectation - which is exactly what a night with two
starters in street clothes should show up in.

The trip terms in the sibling schedule project have been left out; travel is not
what is being asked about here, and the play-by-play mirror this reads does not
carry a venue.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TERMS = {
    "d_b2b": "Second night of a back-to-back",
    "d_games7": "Games in the past week",
    "d_rest": "Days off",
}
OWN = {"d_b2b": "b2b", "d_games7": "games_7d", "d_rest": "rest"}


def game_frame(sched: pd.DataFrame) -> pd.DataFrame:
    """Fold the team-game schedule into one row per game, differenced."""
    home = sched[sched["home"] == 1].set_index("game_id")
    away = sched[sched["home"] == 0].set_index("game_id")
    common = home.index.intersection(away.index)
    home, away = home.loc[common], away.loc[common]

    g = pd.DataFrame({"season": home["season"], "margin": home["margin"],
                      "home": home["team"], "away": away["team"]})
    for term, col in OWN.items():
        g[term] = home[col].to_numpy() - away[col].to_numpy()
    for col in ("rest_night", "prev_rest_night", "n_iso"):
        g[f"h_{col}"] = home[col].to_numpy()
        g[f"a_{col}"] = away[col].to_numpy()
    g["ts_home"] = g["home"] + "_" + g["season"].astype(str)
    g["ts_away"] = g["away"] + "_" + g["season"].astype(str)
    return g.reset_index()


def design(g: pd.DataFrame, terms: list[str]):
    ts = pd.Index(sorted(set(g["ts_home"]) | set(g["ts_away"])))
    seasons = pd.Index(sorted(g["season"].unique()))
    n = len(g)
    X = np.zeros((n, len(ts) + len(seasons) + len(terms)))
    rows = np.arange(n)
    X[rows, ts.get_indexer(g["ts_home"])] += 1.0
    X[rows, ts.get_indexer(g["ts_away"])] -= 1.0
    X[rows, len(ts) + seasons.get_indexer(g["season"])] = 1.0
    for j, term in enumerate(terms):
        X[:, len(ts) + len(seasons) + j] = g[term].to_numpy()
    return X, g["margin"].to_numpy(), ts, seasons


def ols(X: np.ndarray, y: np.ndarray):
    """Least squares with a pseudo-inverse, because the fixed effects are a
    collinear block and read as deviations rather than levels."""
    inv = np.linalg.pinv(X.T @ X)
    beta = inv @ (X.T @ y)
    resid = y - X @ beta
    dof = len(y) - np.linalg.matrix_rank(X)
    se = np.sqrt(np.clip(np.diag(inv) * (resid @ resid) / dof, 0, None))
    return beta, se, 1 - resid.var() / y.var(), resid, dof


def mean_ci(values: np.ndarray) -> tuple[float, float, float, int]:
    """Mean with a normal interval. Games are the unit and they are independent
    enough for this; the caveat is in docs/method.md."""
    v = np.asarray(values, dtype=float)
    n = len(v)
    se = v.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return float(v.mean()), float(v.mean() - 1.96 * se), float(v.mean() + 1.96 * se), n
