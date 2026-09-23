"""Stage 2 - how much the Spurs rested people, and what it bought.

    python src/run_02_rest.py

Three things, in order: how often teams took a planned night off and when San
Antonio started doing it; whether the proxy for a planned night off behaves the
way rest should; and what it was worth on the night, in the next game and in
April.

Writes output/season_rates.csv, output/validation.csv, output/franchises.csv,
output/ledger.csv, output/playoff_effect.csv, output/franchise_playoff_corr.csv,
output/miami_2012.csv, output/model_fit.csv, output/spurs_rest_nights.csv
and figures 01-05.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CHECK_GAME, ERA, FIG, OUT, PROC, TEAM  # noqa: E402
import model as M  # noqa: E402
import style as S  # noqa: E402

S.apply()

MIN_PLAYERS_RESTED = 2   # what makes a game a "planned night off" rather than one absence
MIN_PLAYOFF_GAMES = 4    # a team-season needs a full series to be scored on


def season_label(season: int) -> str:
    return f"{season - 1}-{str(season)[2:]}"


def attach_rest_nights(sched: pd.DataFrame, att: pd.DataFrame) -> pd.DataFrame:
    """Mark each team-game with how many rotation players took an isolated absence."""
    per_game = (att.groupby(["season", "team", "game_id"], observed=True)
                .agg(n_rotation=("athlete_id", "size"),
                     n_iso=("isolated", "sum"),
                     n_missed=("missed", "sum"))
                .reset_index())
    out = sched.merge(per_game, on=["season", "team", "game_id"], how="left")
    out[["n_rotation", "n_iso", "n_missed"]] = out[["n_rotation", "n_iso",
                                                    "n_missed"]].fillna(0)
    out["rest_night"] = (out["n_iso"] >= MIN_PLAYERS_RESTED).astype(int)
    out = out.sort_values(["season", "team", "date"])
    out["prev_rest_night"] = (out.groupby(["season", "team"], sort=False)["rest_night"]
                              .shift(1).fillna(0))
    return out


def validation(att: pd.DataFrame) -> pd.DataFrame:
    """Does the proxy behave like rest, or like injury?

    An isolated absence should track the things a coach schedules around. A long
    absence should not track them at all - a ligament does not know it is a
    back-to-back. If both moved together the proxy would be measuring nothing.
    """
    d = att.copy()
    d["long_absence"] = ((d["missed"] == 1) & (d["isolated"] == 0)).astype(int)
    rows = []
    for rest, block in d.groupby("rest", observed=True):
        rows.append({"situation": f"{int(rest)} days off" if rest < 3 else "3+ days off",
                     "games": len(block),
                     "isolated_rate": float(block["isolated"].mean()),
                     "long_absence_rate": float(block["long_absence"].mean())})
    quart = pd.qcut(d["opp_margin"], 4,
                    labels=["weakest quarter of opponents", "second", "third",
                            "strongest quarter of opponents"])
    for label, block in d.groupby(quart, observed=True):
        rows.append({"situation": str(label), "games": len(block),
                     "isolated_rate": float(block["isolated"].mean()),
                     "long_absence_rate": float(block["long_absence"].mean())})
    return pd.DataFrame(rows)


def ledger(g: pd.DataFrame, resid: np.ndarray) -> pd.DataFrame:
    """The three numbers the project exists to produce.

    Each is a mean residual margin, pooled over the two sides so that a night
    off is priced the same whoever took it.
    """
    d = g.assign(resid=resid)
    def pooled(home_mask, away_mask):
        return np.r_[d.loc[home_mask, "resid"].to_numpy(),
                     -d.loc[away_mask, "resid"].to_numpy()]

    on_night = pooled(d["h_rest_night"] == 1, d["a_rest_night"] == 1)
    after = pooled(d["h_prev_rest_night"] == 1, d["a_prev_rest_night"] == 1)
    neither = pooled((d["h_rest_night"] == 0) & (d["h_prev_rest_night"] == 0),
                     (d["a_rest_night"] == 0) & (d["a_prev_rest_night"] == 0))
    rows = []
    for label, v in (("On a night two or more sat", on_night),
                     ("The next game", after),
                     ("Every other game", neither)):
        mean, lo, hi, n = M.mean_ci(v)
        rows.append({"split": label, "games": n, "margin_vs_expected": mean,
                     "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def playoff_effect(playoffs: pd.DataFrame, strength: pd.Series, hca: pd.Series,
                   rest_rate: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Did resting in the regular season buy anything in April?

    Each postseason game gets the margin the regular-season model expects from
    the two teams' own season strengths and who was at home. The average
    residual is how much better a team played in the playoffs than its regular
    season said it would.
    """
    p = playoffs.copy()
    p["ts"] = p["team"] + "_" + p["season"].astype(str)
    p["ots"] = p["opponent"] + "_" + p["season"].astype(str)
    p = p[p["ts"].isin(strength.index) & p["ots"].isin(strength.index)]
    p["expected"] = (strength.reindex(p["ts"]).to_numpy()
                     - strength.reindex(p["ots"]).to_numpy()
                     + np.where(p["home"] == 1, 1, -1)
                     * hca.reindex(p["season"]).to_numpy())
    p["over"] = p["margin"] - p["expected"]

    by_team = (p.groupby(["season", "team"], observed=True)
               .agg(playoff_games=("over", "size"), over=("over", "mean"))
               .reset_index())
    d = by_team.merge(rest_rate, on=["season", "team"], how="inner")
    d = d[d["playoff_games"] >= MIN_PLAYOFF_GAMES]

    slope, intercept = np.polyfit(d["rest_rate"], d["over"], 1)
    resid = d["over"] - (slope * d["rest_rate"] + intercept)
    se = resid.std(ddof=2) / (d["rest_rate"].std(ddof=1) * np.sqrt(len(d) - 1))
    fit = {"slope_per_10pp": float(slope) * 0.10, "se_per_10pp": float(se) * 0.10,
           "t": float(slope / se), "n": int(len(d)),
           "r": float(np.corrcoef(d["rest_rate"], d["over"])[0, 1])}
    return d, fit


def fig_league_trend(rates: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.6, 5.2))
    ax.plot(rates["season"], 100 * rates["league"], color=S.SILVER, lw=2.4, zorder=3)
    ax.plot(rates["season"], 100 * rates["spurs"], color=S.SPURS, lw=2.2, zorder=4)
    ax.scatter(rates["season"], 100 * rates["spurs"], s=22, color=S.SPURS, zorder=5,
               edgecolors=S.SURFACE, lw=1.1)
    ax.annotate("the league", (rates["season"].iloc[-1], 100 * rates["league"].iloc[-1]),
                xytext=(8, -2), textcoords="offset points", va="center",
                color=S.INK_3, fontsize=9.4, fontweight="semibold")
    ax.annotate("San Antonio", (rates["season"].iloc[-1], 100 * rates["spurs"].iloc[-1]),
                xytext=(8, 0), textcoords="offset points", va="center",
                color=S.SPURS, fontsize=9.4, fontweight="semibold")
    ax.axvspan(ERA[0] - 0.4, 2009.5, color=S.NEUTRAL, alpha=0.28, zorder=1)
    ax.annotate("two titles, almost nobody rested", (2004.0, 9.2), fontsize=9,
                color=S.INK_2, ha="left")
    S.strip(ax)
    ax.set_xlim(2003.4, 2027.6)
    ax.set_ylim(0, 10.4)
    ax.set_xticks(range(2004, 2024, 3), [season_label(v) for v in range(2004, 2024, 3)])
    ax.tick_params(axis="x", labelsize=8.8)
    ax.set_yticks(range(0, 11, 2), [f"{v}%" for v in range(0, 11, 2)])
    ax.set_ylabel("Share of rotation player-games missed\nin an isolated one- or two-game absence")
    ax.set_title("The reputation is real, and it arrives about a decade late", loc="left")
    S.caption(fig, "An isolated absence is one or two games missed with games played on both "
                   "sides, inside one season - the shape a planned night off makes and an injury "
                   "usually does not. Rotation players only: 40 or more games at 20 or more "
                   "minutes for that team that season.")
    fig.tight_layout()
    fig.savefig(FIG / "01_league_trend.png")
    plt.close(fig)


def fig_validation(v: pd.DataFrame) -> None:
    d = v[v["situation"].str.contains("days off")].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    x = np.arange(len(d))
    w = 0.36
    ax.bar(x - w / 2, 100 * d["isolated_rate"], w, color=S.SPURS, zorder=3,
           label="isolated absence (one or two games)")
    ax.bar(x + w / 2, 100 * d["long_absence_rate"], w, color=S.SILVER, zorder=3,
           label="longer absence")
    for xi, val in zip(x - w / 2, d["isolated_rate"]):
        ax.text(xi, 100 * val + 0.25, f"{100 * val:.1f}%", ha="center", fontsize=9,
                color=S.INK, fontweight="semibold")
    for xi, val in zip(x + w / 2, d["long_absence_rate"]):
        ax.text(xi, 100 * val + 0.25, f"{100 * val:.1f}%", ha="center", fontsize=9,
                color=S.INK_2)
    ax.set_xticks(x, d["situation"])
    ax.set_ylim(0, 16)
    ax.set_yticks(range(0, 16, 5), [f"{v}%" for v in range(0, 16, 5)])
    ax.set_ylabel("Share of rotation player-games missed")
    ax.set_title("The proxy behaves like rest, and the alternative does not", loc="left")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    S.strip(ax)
    ax.grid(axis="x", visible=False)
    S.caption(fig, "Isolated absences more than double from three days off to none. Longer "
                   "absences barely move, because a torn ligament does not know it is a "
                   "back-to-back. That gap is the only evidence this project has that the "
                   "isolated ones are planned, and it is the reason the rest of it is possible.")
    fig.tight_layout()
    fig.savefig(FIG / "02_validation.png")
    plt.close(fig)


def fig_franchises(fr: pd.DataFrame) -> None:
    d = fr.nlargest(14, "rest_night_rate").sort_values("rest_night_rate").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    colours = [S.SPURS if t == TEAM else S.SILVER for t in d["team"]]
    ax.barh(d.index, 100 * d["rest_night_rate"], color=colours, height=0.62, zorder=2)
    for i, r in d.iterrows():
        ax.text(100 * r["rest_night_rate"] + 0.06, i,
                f"{100 * r['rest_night_rate']:.1f}%   {int(r['nights'])} nights",
                va="center", fontsize=8.6,
                color=S.INK if r["team"] == TEAM else S.INK_2,
                fontweight="semibold" if r["team"] == TEAM else "normal")
    ax.set_yticks(d.index, d["team"])
    ax.set_ylim(-0.75, len(d) - 0.25)
    ax.set_xlim(0, 100 * d["rest_night_rate"].max() * 1.5)
    ax.grid(axis="y", visible=False)
    S.strip(ax, keep=("bottom",))
    ax.set_xlabel("Share of games with two or more rotation players taking a planned night off")
    ax.set_title("Nobody else does it as often", loc="left")
    S.caption(fig, "2003-04 to 2022-23, regular season. A night counts when two or more of a "
                   "team's rotation players are all absent for one or two games with games "
                   "played on either side.")
    fig.tight_layout()
    fig.savefig(FIG / "03_franchises.png")
    plt.close(fig)


def fig_ledger(led: pd.DataFrame, fit: dict) -> None:
    rows = [
        ("On the night two or more sit", led.loc[0, "margin_vs_expected"],
         led.loc[0, "lo"], led.loc[0, "hi"], int(led.loc[0, "games"])),
        ("In the next game", led.loc[1, "margin_vs_expected"],
         led.loc[1, "lo"], led.loc[1, "hi"], int(led.loc[1, "games"])),
        ("In the playoffs, per 10 pp\nof extra rest across a season",
         fit["slope_per_10pp"], fit["slope_per_10pp"] - 1.96 * fit["se_per_10pp"],
         fit["slope_per_10pp"] + 1.96 * fit["se_per_10pp"], fit["n"]),
    ]
    d = pd.DataFrame(rows, columns=["label", "beta", "lo", "hi", "n"]).iloc[::-1]
    d = d.reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    sig = (d["lo"] > 0) | (d["hi"] < 0)
    ax.barh(d.index, d["beta"], height=0.4, zorder=2,
            color=[S.SPURS if s_ else S.SILVER for s_ in sig])
    ax.errorbar(d["beta"], d.index, xerr=[d["beta"] - d["lo"], d["hi"] - d["beta"]],
                fmt="none", ecolor=S.INK_2, elinewidth=1.2, capsize=3.5, zorder=3)
    span = float(d["hi"].max() - d["lo"].min())
    for i, r in d.iterrows():
        end = r["lo"] if r["beta"] < 0 else r["hi"]
        ax.text(end + np.sign(r["beta"] or 1) * 0.02 * span, i,
                f"{r['beta']:+.2f}   n = {int(r['n']):,}", va="center",
                ha="left" if r["beta"] >= 0 else "right", fontsize=9.2,
                color=S.INK_2)
    ax.axvline(0, color=S.INK_3, lw=0.9, zorder=4)
    ax.set_yticks(d.index, d["label"])
    ax.set_xlim(d["lo"].min() - 0.30 * span, d["hi"].max() + 0.30 * span)
    ax.set_ylim(-0.7, len(d) - 0.3)
    ax.grid(axis="y", visible=False)
    S.strip(ax, keep=("bottom",))
    ax.tick_params(axis="y", labelsize=9.2)
    ax.set_xlabel("Margin above what the model expects, points per game")
    ax.set_title("One of these is measurable", loc="left")
    S.caption(fig, "All three are residuals from the same fit: team-season strengths, "
                   "season-by-season home advantage, rest, density. The cost is a real number "
                   "with a tight interval. The two benefits are indistinguishable from zero, "
                   "which is not the same as knowing they are zero - see the README.")
    fig.tight_layout()
    fig.savefig(FIG / "04_ledger.png")
    plt.close(fig)


def franchise_correlations(d: pd.DataFrame, min_seasons: int = 8) -> pd.DataFrame:
    """The same within-team correlation, for everybody.

    San Antonio's own sixteen postseasons are the evidence that made people
    believe this in the first place. Running the identical calculation on every
    franchise says what that evidence is worth.
    """
    rows = []
    for team, block in d.groupby("team", observed=True):
        if len(block) < min_seasons or block["rest_rate"].std() == 0:
            continue
        rows.append({"team": team, "seasons": len(block),
                     "r": float(np.corrcoef(block["rest_rate"], block["over"])[0, 1])})
    return pd.DataFrame(rows).sort_values("r", ascending=False).reset_index(drop=True)


def fig_playoffs(d: pd.DataFrame, fit: dict, corr: pd.DataFrame) -> None:
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.0, 5.2),
                                  gridspec_kw={"width_ratios": [1.35, 1]})
    others = d[d["team"] != TEAM]
    ax.scatter(100 * others["rest_rate"], others["over"], s=22, color=S.NEUTRAL,
               linewidths=0, zorder=2)
    sa = d[d["team"] == TEAM]
    ax.scatter(100 * sa["rest_rate"], sa["over"], s=38, color=S.SPURS, zorder=4,
               edgecolors=S.SURFACE, lw=1.1)
    xs = np.linspace(0, 100 * d["rest_rate"].max(), 40)
    b = np.polyfit(100 * d["rest_rate"], d["over"], 1)
    ax.plot(xs, np.polyval(b, xs), color=S.SERIES[1], lw=2, zorder=3)
    ax.axhline(0, color=S.INK_3, lw=0.9, zorder=2)
    S.strip(ax)
    ax.set_xticks(range(0, 12, 2), [f"{v}%" for v in range(0, 12, 2)])
    ax.set_xlabel("Share of the regular season spent\nresting two or more rotation players")
    ax.set_ylabel("Playoff margin above what their\nregular season predicts, per game")
    ax.set_title("Across the league, nothing", loc="left", fontsize=11)

    order = corr.sort_values("r").reset_index(drop=True)
    colours = [S.SPURS if t == TEAM else S.SILVER for t in order["team"]]
    ax2.barh(order.index, order["r"], color=colours, height=0.66, zorder=2)
    ax2.axvline(0, color=S.INK_3, lw=0.9, zorder=3)
    sa_row = order.index[order["team"] == TEAM][0]
    ax2.annotate(f"San Antonio {order.loc[sa_row, 'r']:+.2f}",
                 (order.loc[sa_row, "r"], sa_row), xytext=(7, 0),
                 textcoords="offset points", va="center", fontsize=9,
                 color=S.SPURS, fontweight="semibold")
    ax2.set_yticks([])
    ax2.set_xlim(-0.9, 1.15)
    ax2.set_ylim(-0.8, len(order) - 0.2)
    ax2.grid(axis="y", visible=False)
    S.strip(ax2, keep=("bottom",))
    ax2.set_xlabel("Correlation inside one franchise's own seasons")
    ax2.set_title("Inside one team, anything", loc="left", fontsize=11)

    S.caption(fig, f"Left: {fit['n']} playoff team-seasons, 2003-04 to 2021-22, San Antonio in "
                   f"black; the slope is {fit['slope_per_10pp']:+.2f} points per ten percentage "
                   f"points of extra rest against a standard error of "
                   f"{fit['se_per_10pp']:.2f}. Right: the same correlation computed inside each "
                   f"franchise with eight or more postseasons. San Antonio's own record is the "
                   f"evidence everyone has in mind, and it sits in the right tail of a "
                   f"distribution centered on nothing. The 2022-23 postseason is not in the "
                   f"mirror this reads.")
    fig.tight_layout()
    fig.savefig(FIG / "05_playoffs.png")
    plt.close(fig)


def main() -> None:
    att = pd.read_csv(PROC / "attendance.csv.gz", low_memory=False)
    sched = pd.read_csv(PROC / "schedule.csv.gz", low_memory=False)
    playoffs = pd.read_csv(PROC / "playoffs.csv.gz", low_memory=False)

    sched = attach_rest_nights(sched, att)

    # --- how much, and when ---------------------------------------------
    league = att.groupby("season")["isolated"].mean().rename("league")
    spurs = att[att["team"] == TEAM].groupby("season")["isolated"].mean().rename("spurs")
    by_team = att.groupby(["season", "team"], observed=True)["isolated"].mean().reset_index()
    by_team["rank"] = by_team.groupby("season")["isolated"].rank(ascending=False,
                                                                method="min")
    rates = pd.concat([league, spurs], axis=1).reset_index()
    rates = rates.merge(by_team.loc[by_team["team"] == TEAM, ["season", "rank"]],
                        on="season", how="left")
    nights = (sched.groupby(["season", "team"], observed=True)
              .agg(games=("rest_night", "size"), nights=("rest_night", "sum"),
                   rest_rate=("rest_night", "mean")).reset_index())
    nights["night_rank"] = nights.groupby("season")["rest_rate"].rank(ascending=False,
                                                                     method="min")
    rates = rates.merge(nights.loc[nights["team"] == TEAM,
                                   ["season", "nights", "rest_rate", "night_rank"]],
                        on="season", how="left")
    rates.round(5).to_csv(OUT / "season_rates.csv", index=False)
    nights.round(5).to_csv(OUT / "spurs_rest_nights.csv", index=False)

    fr = (nights.groupby("team")
          .agg(seasons=("season", "size"), games=("games", "sum"),
               nights=("nights", "sum")).reset_index())
    fr["rest_night_rate"] = fr["nights"] / fr["games"]
    fr.sort_values("rest_night_rate", ascending=False).round(5).to_csv(
        OUT / "franchises.csv", index=False)

    # --- is the proxy measuring rest? ------------------------------------
    v = validation(att)
    v.round(5).to_csv(OUT / "validation.csv", index=False)

    # --- what it was worth -----------------------------------------------
    g = M.game_frame(sched)
    terms = list(M.TERMS)
    X, y, ts, seasons = M.design(g, terms)
    beta, se, r2, resid, dof = M.ols(X, y)
    coef = pd.DataFrame({"term": terms, "beta": beta[len(ts) + len(seasons):],
                         "se": se[len(ts) + len(seasons):],
                         "label": [M.TERMS[t] for t in terms]})
    coef.round(4).to_csv(OUT / "schedule_terms.csv", index=False)

    led = ledger(g, resid)
    led.round(4).to_csv(OUT / "ledger.csv", index=False)
    overlap = int(((g["h_rest_night"] == 1) & (g["h_prev_rest_night"] == 1)).sum()
                  + ((g["a_rest_night"] == 1) & (g["a_prev_rest_night"] == 1)).sum())
    pd.DataFrame([{"r2": r2, "residual_sd": float(resid.std()), "games": len(g),
                   "rest_night_and_next_game_overlap": overlap}]).round(4).to_csv(
        OUT / "model_fit.csv", index=False)

    strength = pd.Series(beta[:len(ts)], index=ts)
    hca = pd.Series(beta[len(ts):len(ts) + len(seasons)], index=seasons)
    po, fit = playoff_effect(playoffs, strength, hca,
                             nights[["season", "team", "rest_rate"]])
    po.round(5).to_csv(OUT / "playoff_effect.csv", index=False)
    pd.DataFrame([fit]).round(5).to_csv(OUT / "playoff_fit.csv", index=False)

    fig_league_trend(rates)
    fig_validation(v)
    fig_franchises(fr)
    fig_ledger(led, fit)
    corr = franchise_correlations(po)
    corr.round(4).to_csv(OUT / "franchise_playoff_corr.csv", index=False)
    fig_playoffs(po, fit, corr)

    # A single named game, as a check on the rule rather than on the answer.
    check = att[(att["team"] == TEAM) & (att["date"].astype(str).str[:10] == CHECK_GAME)]
    check = check[["player", "played", "dnp", "absent", "isolated", "run_len"]]
    check.to_csv(OUT / "miami_2012.csv", index=False)
    print(f"--- {CHECK_GAME}, the game the rule was never told about ---")
    print(check.to_string(index=False))
    print()

    print("--- planned nights off, San Antonio against the league ---")
    print(rates.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    era = rates[(rates["season"] >= ERA[0]) & (rates["season"] <= 2009)]
    print(f"\n{ERA[0]}-2009, two championships: {int(era['nights'].sum())} nights with two or "
          f"more rested, against a league rate of {100 * era['league'].mean():.1f}% of "
          f"player-games isolated and San Antonio's {100 * era['spurs'].mean():.1f}%")

    print("\n--- is an isolated absence actually rest? ---")
    print(v.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n--- who does it most, twenty seasons ---")
    print(fr.nlargest(6, "rest_night_rate").to_string(index=False,
                                                      float_format=lambda x: f"{x:.4f}"))

    print(f"\nmodel: R² {r2:.4f}, residual SD {resid.std():.2f}, {len(g):,} games")
    print(coef[["label", "beta", "se"]].to_string(index=False,
                                                  float_format=lambda x: f"{x:.3f}"))

    print("\n--- the ledger ---")
    print(led.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(f"(the first two rows overlap: {overlap} games are both)")
    print(f"\nplayoffs: {fit['slope_per_10pp']:+.2f} points per 10 pp of rest "
          f"(se {fit['se_per_10pp']:.2f}, t {fit['t']:.2f}, r {fit['r']:+.3f}, "
          f"n {fit['n']})")

    sa = po[po["team"] == TEAM].sort_values("season")
    sa_corr = corr.loc[corr["team"] == TEAM, "r"].iloc[0]
    print(f"\ninside San Antonio's own {int(po[po['team'] == TEAM].shape[0])} postseasons: "
          f"r = {sa_corr:+.3f}, which ranks "
          f"{int((corr['r'] > sa_corr).sum()) + 1} of {len(corr)} franchises")
    print(corr.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print(f"\n--- San Antonio in the playoffs ---")
    print(sa[["season", "rest_rate", "playoff_games", "over"]]
          .to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
