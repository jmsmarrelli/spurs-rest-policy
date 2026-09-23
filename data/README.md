# Data

One file per season at `data/raw/player_box/player_box_<season>.csv.gz`, where
`<season>` is the year the season ended: `player_box_2016.csv.gz` is 2015-16.

## Getting the files

From [sportsdataverse/hoopR-data](https://github.com/sportsdataverse/hoopR-data),
a mirror of ESPN's public feeds.

```bash
git clone --filter=blob:none --no-checkout --depth 1 \
  https://github.com/sportsdataverse/hoopR-data.git /tmp/hoopR-data
cd /tmp/hoopR-data
git sparse-checkout set --no-cone "nba/player_box/csv/*"
git checkout
cd -
mkdir -p data/raw/player_box
cp /tmp/hoopR-data/nba/player_box/csv/player_box_20*.csv.gz data/raw/player_box/
```

About 45 MB — this is the whole project's input. `data/raw/` and
`data/processed/` are gitignored; everything the analysis cites is written to
`output/` and committed.

## The column that does not exist

**There is no reason field.** The box score records that a player did not play.
It does not record whether that was a knee, a coach, a suspension, a funeral or
a newborn. Every "rest" in this repository is an inference from the *shape* of
the absence, never a label read off the file, and `docs/method.md` sets out how
far that inference can be pushed.

Three related things the file does record, which matter:

* `did_not_play` — dressed and unused. Distinct from not appearing at all.
* absence of a row — not on the active list. A player who is rested in the
  modern NBA usually lands here; a deep reserve on a blowout night lands in
  `did_not_play`.
* `minutes` — null whenever either of the above is true.

The mix between the two shifted over the sample as teams changed how they
reported inactives, which is why this project treats them together as "missed"
and never separates rest from injury by which of the two it was.

## Columns used

| Column | Used for |
|---|---|
| `game_id`, `season`, `season_type`, `game_date` | joining, and the regular-season / postseason split |
| `athlete_id`, `athlete_display_name` | who |
| `team_abbreviation`, `opponent_team_abbreviation` | which team, and against whom |
| `minutes`, `did_not_play` | played, dressed-and-unused, or absent |
| `team_score`, `opponent_team_score`, `home_away` | the margin and home advantage |
| `starter`, `points`, `plus_minus` | carried through the panel, not used in a headline |

## Filters

Regular season for the attendance panel and the margin model, postseason for the
April test. Both sides drop rows whose team is not one of the 32 franchise codes,
which removes the All-Star Game — the mirror files it under the same season type
as the regular season, and it would otherwise appear as a night on which almost
every rotation player in the league was absent.

The 2022-23 postseason is not in this mirror, so the playoff test covers nineteen
postseasons, 2003-04 to 2021-22.
