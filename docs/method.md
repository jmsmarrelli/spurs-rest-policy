# Method notes

What an absence is, how far the proxy can be pushed, and the three reasons the
null at the end is not a finding that rest does not work.

## The definitional problem, stated once

The public box score has a flag for "did not play" and it has the absence of a
row. Neither carries a reason. There is no rest field, there never was one, and
no amount of care with the rest of the file conjures one up.

So the object of study is the **shape** of an absence, not its cause:

* **isolated** — one or two games missed, with games played on both sides, inside
  a single season.
* **everything else** — longer runs, and absences that run to the end or start of
  a season.

Isolated absences are treated as *probably planned*. Longer ones are not treated
as injuries; they are left unlabelled, because a ten-game absence can be a knee,
a suspension or a trade, and the file does not say.

## Why the proxy is believable

Three checks, in increasing order of how much they are worth.

**One famous game.** On 29 November 2012 Popovich sent Duncan, Parker, Ginóbili
and Green home from Miami before a nationally televised game; the league fined
the franchise $250,000. The rule is given no dates and no names, and it flags
exactly those four as isolated one-game absences while leaving Kawhi Leonard's
eighteen-game absence in the same stretch unflagged. That is one game and it
proves nothing, but a rule that failed it would not be worth continuing with.
`output/miami_2012.csv`.

**The dose-response on rest.** Isolated absences run 3.80% on the second night of
a back-to-back, 2.58% on one day's rest, 2.46% on two and 1.85% on three or
more — monotone, and more than double end to end.

This one is the *single-player* rate: any rotation player taking an isolated
absence. The two-player "planned night off" is the unit for everything that
follows about how often teams did it and what it cost, but the validation is
better done on the larger sample.

**The placebo on the same axis.** Longer absences run 12.88%, 12.62%, 11.82% and
11.17% across the same four situations. A gradient of 1.7 points against the
isolated measure's 1.9, on a base five times the size. Injuries do not care
what the schedule looks like; planned absences visibly do. That contrast is the
whole licence for the rest of the project.

**What the checks do not establish.** That every isolated absence is rest. A
one-game illness, a bereavement, a one-game suspension and a minor sprain all
make the same shape. The measure is a rate of *probably planned* absences, and
the noise in it works against finding an effect rather than manufacturing one.

## Who counts as a rotation player

Forty or more games at twenty or more minutes for that team, that season. Both
floors are needed: minutes alone lets a twenty-game call-up in, games alone lets
a deep reserve in. 4,238 player-seasons qualify, about 210 a season.

The floor is applied *within a season*, which has a consequence worth naming: a
player who is rested so heavily that he falls below forty games stops being a
rotation player and his absences disappear from the panel. That biases the
measured rest rate down in exactly the seasons the project is most interested in,
so the trend in figure 01 is if anything conservative.

## A "planned night off"

Two or more rotation players taking an isolated absence in the same game. One
absence is a player; two at once is a decision.

The counts, ranks and the whole ledger use the two-player version. The
single-player rate is what figure 01 and the validation table run on, because
they need the larger sample and do not need the stronger definition; it is in
`output/season_rates.csv` and tells the same story more quietly.

## The margin model

One row per game from the home side; the outcome is the final margin.

    margin = strength(home, season) - strength(away, season)
           + home advantage for the season
           + back-to-backs, days off, games in the past week (differenced)
           + error

R² 0.228, residual standard deviation 11.8 points across 23,934 games. A
back-to-back is worth −1.78, each extra game in the trailing week −0.33 — both
close to the independent fits in the sibling schedule projects, which is the
cross-check that the residuals mean what they are being asked to mean.

Team-season effects are doing something specific here. A team that rests a lot is
a team with a good roster and old legs; the fixed effect absorbs its average
strength, so the residual on a rest night is that team against *itself*, not
against the league.

What the fixed effect cannot absorb is *when in the season* the resting happened.
A team that rests in April, after the seed is settled, is a team whose
regular-season strength is being measured partly on games it was not trying to
win. That is a real bias and it is not corrected here.

## The playoff test, and why the Spurs' own record is a trap

For each postseason game, the expected margin is the two teams' regular-season
strengths plus that season's home advantage. The residual, averaged over a
team's postseason, is how much better it played than its regular season implied.
Regressed on that team's regular-season rest-night rate over 304 playoff
team-seasons — every one that played at least four postseason games, which in
this sample is all of them: −0.73 points per ten percentage points of rest,
standard error 1.19.

Then the same correlation *inside* each franchise's own seasons. San Antonio's is
+0.45 across sixteen postseasons and ranks 2nd of 23 franchises with eight or
more. Thirteen are negative and four are below −0.55. The between-franchise spread
is enormous and centered on zero, which is what sixteen noisy observations look
like when you go looking inside the one case that generated the hypothesis.

This is the most useful thing in the repository. The Spurs' record is real, it
points the right way, and it is not evidence — because the same calculation on
twenty-two other franchises produces a distribution that contains it comfortably.

## Where this is weakest

**Availability is not measured.** The mechanism people actually mean is that the
star is on the floor in May rather than in a suit. A model of playoff *margin*
prices how well a team played, not whether its best player was available at all.
If resting works, this is probably where it works, and this design cannot see it.
Testing it needs injury data, which is not in this file and is not reliably
public anywhere.

**The intervals are wide enough to matter.** The playoff slope's interval runs
from −3.1 to +1.6 points a game. A front office would care a great deal about
either end of that. "Not distinguishable from zero" is not "zero", and the
difference is the entire practical question.

**The ledger's first two rows overlap.** 110 of the 971 games following a rest
night were rest nights themselves. The "every other game" row is the complement
of the union rather than the third slice of a partition, and the bounce estimate
carries a little of the cost inside it.

**Games are treated as independent** when computing the intervals on the ledger.
Rest nights cluster within a team-season, so the true intervals are somewhat
wider than the ones quoted. It does not change the sign or the order of magnitude
of the −2.70, which is the only thing that number is used for.

**Selection into resting is not random and is only partly controlled.** Teams
rest when they are old, when the seed is won, and when a player is nursing
something minor that never becomes an injury absence. The third of those is the
worst: it means the "planned" absences are enriched for players who were slightly
hurt, which is exactly the population whose next game would be worse anyway.

**Regular season only for the ledger, 2003-04 to 2022-23; nineteen postseasons
for the April test**, because the 2022-23 playoffs are not in the mirror this
reads.
