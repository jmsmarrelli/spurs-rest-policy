"""Paths, seasons and the definitions this project has to make explicit."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
FIG = ROOT / "figures"
OUT = ROOT / "output"

for d in (RAW, PROC, FIG, OUT):
    d.mkdir(parents=True, exist_ok=True)

# Season label is the year the season ends: 2016 == 2015-16.
FIRST_SEASON = 2004
LAST_SEASON = 2023
SEASONS = list(range(FIRST_SEASON, LAST_SEASON + 1))

TEAM = "SA"
TEAM_NAME = "San Antonio Spurs"

# Gregg Popovich's Spurs, taken as the Duncan era: his rookie-of-the-year season
# is out of reach of the play-by-play feed, so the window here is the part of it
# this data can see, ending with his retirement.
ERA = (2004, 2016)

# Who counts as a rotation player. Both floors are needed: minutes alone lets a
# 20-game call-up in, games alone lets a deep reserve in.
MIN_GAMES_PLAYED = 40
MIN_MINUTES_PER_GAME = 20.0

# An absence is "isolated" when the player missed this many games in a row or
# fewer, with games played on both sides of it inside the same season. It is a
# proxy for a planned night off and it is not a label the data carries; see
# docs/method.md for how far it can be trusted.
MAX_ISOLATED_RUN = 2

# The most famous planned night off in the league's history: 29 November 2012,
# Popovich sends four players home from Miami before a nationally televised game
# and the league fines the franchise $250,000. The detector knows nothing about
# it and is checked against it.
CHECK_GAME = "2012-11-29"

SEED = 20240117
