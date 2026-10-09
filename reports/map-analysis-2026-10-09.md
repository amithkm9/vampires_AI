# Exact map analysis

The supplied maps reward safe approach squares, population thresholds, and denying the opponent access to humans. This analysis verifies local facts; it does not solve either full game or establish a tournament win rate.

## Method and reproduction

```sh
python3 tools/analyze_maps.py --output reports/map-analysis-2026-10-09.json
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The [JSON record](map-analysis-2026-10-09.json) includes map/code hashes, Python and platform versions, configuration, exact rational probabilities, and runtime. No random seed is needed: the calculations enumerate outcomes rather than sample them. The recorded run took approximately 0.017 seconds; all 56 tests passed. This is an offline analysis runtime, not measured AI turn time.

`simulation.battle_distribution` enumerates the winner and binomial survivor distributions. `simulation.single_move_outcomes` preserves the input board and models one move record. `tools/analyze_maps.py` audits local replies and enumerates optimistic house orders. Multi-record combat and official-server parity remain unverified.

## The trap map

The board is 10 columns by 5 rows. Werewolves start with 4 at `(4,1)`, vampires with 4 at `(4,3)`, and the largest house contains 4 humans at `(2,2)`. The three right-edge houses contain `2+1+2=5` humans. Total population including humans is 17.

The table assumes the named species is the first player to move from the original board. Reply analysis includes every amount in every legal one-record opponent move. An arbitrary later board must be analyzed again.

| First mover | First move carrying all 4 | Moves still needed to left house | Largest next-reply extinction probability |
| --- | --- | ---: | ---: |
| Werewolves | `(4,1) -> (3,2)` | 1 | `17/32 = 53.125%` |
| Werewolves | `(4,1) -> (3,1)` | 1 | `0%` |
| Vampires | `(4,3) -> (3,2)` | 1 | `17/32 = 53.125%` |
| Vampires | `(4,3) -> (3,3)` | 1 | `0%` |

The exposed square `(3,2)` is adjacent to the opponent's starting stack. Its full-strength attack produces three categories: our species alone survives with probability `15/32`, the opponent alone survives with probability `15/32`, and both disappear with probability `1/16`. Therefore 53.125% is an extinction probability, not a reported match-loss probability: it includes the both-empty outcome, whose official result is unspecified.

The safe approach reaches the same house in two of our turns and cannot be attacked on the immediate reply. Under the written rules, the first mover following this line can capture the house on its second turn: the opponent cannot reach the house in one move, and cannot stop an 8-creature conversion by occupying an adjacent square. This guarantees that local capture, not the match.

The left house is not the whole strategy. If one side ends with just that house it has 8; a side that eventually captures all right houses has 9. Whether it can safely do so depends on interception and move order. The engine needs the growth race after the opening, not a hardcoded instruction to pursue the left house forever.

## The large map

The board is 29 columns by 15 rows. Both species start with 10. The human groups are 2 at `(0,14)`, 4 at `(10,3)`, 20 at `(14,7)`, 4 at `(18,11)`, and 2 at `(28,0)`. Total population including humans is 52.

| Human house | Size | Werewolf travel lower bound | Vampire travel lower bound |
| --- | ---: | ---: | ---: |
| `(0,14)` | 2 | 14 | 28 |
| `(10,3)` | 4 | 10 | 18 |
| `(14,7)` | 20 | 14 | 14 |
| `(18,11)` | 4 | 18 | 10 |
| `(28,0)` | 2 | 28 | 14 |

Distances are Chebyshev distances in each player's own moves. They omit threats, incidental occupied squares, and the alternating-turn phase. Arrival is not the same as being strong enough to convert.

### The resource bottleneck

There are only 12 humans outside the center. Each side needs to add 10 to reach a guaranteed central conversion, so both cannot do so. More strongly, once the opponent captures either four-human house, our maximum population from all other peripheral humans is `10 + (12-4) = 18`, even if we take every remaining one and suffer no losses. Monster battles do not convert enemy monsters into our species.

Thus, if each side takes one four-human house, the untouched central 20-human group is inaccessible to deterministic conversion for both. A later random battle may change that house's size; the resource bound is specifically about capturing the original untouched group safely. This makes capturing and denying a four-human house strategically significant.

### A central gamble is expensive

| Attackers against 20 humans | Battle-winning draw probability | Unconditional expected attacking survivors |
| ---: | ---: | ---: |
| 10 | 25% | 1.875 |
| 14 | 35% | 4.165 |
| 18 | 45% | 7.695 |
| 19 | 47.5% | 8.799375 |
| 20 | 100%, deterministic conversion | 40 |

For example, 14 attackers win the initial draw with probability .35. Conditional on winning, survivors follow `Binomial(34,.35)` with mean 11.9. Across wins and losses, the mean is 4.165. The exact probability of emerging with at least 20 creatures is approximately 0.135%, not 35%. A battle win can still leave no survivors.

This does not prove that every central gamble is a bad decision. When safe play is losing, a gamble can be the best available option. It does show why the AI must evaluate the survivor distribution and opponent response rather than treating a won battle as `14+20=34` survivors.

### An uncontested route is not a winning opening

Exhaustive enumeration of feasible house orders for one unsplit stack gives a best optimistic central-conversion arrival of 37 own moves for either side. The werewolf order is `(0,14):2 -> (10,3):4 -> (18,11):4 -> (14,7):20`, with arrival lower bounds `14,25,33,37` and populations `12,16,20,40`. The vampire route is its 180-degree counterpart.

The calculation ignores the opponent and treats travel as empty-board distance. It is a lower bound within that single-stack route model, not an exact path under opposition, a lower bound for split strategies, or a recommended opening. In particular, the opponent can reach its nearby four-human house much earlier than this plan reaches it. The 36 feasible house orders per species are not 36 safe strategies.

### Once a 40-stack exists

Converting the center with 20 creatures creates 40, leaving at most 12 total humans and monsters elsewhere. Under the brief, an intact 40-stack cannot lose creatures against any army the opponent can subsequently assemble. It also remains the dominant population at a finite game end. The AI should preserve this winning condition instead of fragmenting the army or seeking unnecessary uncertainty. This consequence assumes official-server behavior follows the written rules.

## Code added and limits

- Exact rational battle outcomes, including the combined zero-survivor outcome.
- All legal one-record moves with every partial amount.
- One-record transitions for empty movement, partial moves, friendly merges, human conversion, and monster/human battles.
- Explicit failure when a possible successor exceeds the unresolved 255-per-cell representation limit. This cannot occur on the supplied maps under the stated rules because their total populations are only 17 and 52.
- Regression tests for the map facts, probability normalization, analytic expectations, input immutability, and a forced-loss counterexample to universal victory.

There is no complete game solver, live player, joint-turn model, official-server validation, or match benchmark in this report. Those remain the next implementation and validation steps in [the strategy design](../docs/STRATEGY.md).
