# Game and assignment rules

The authority is [Projectv10.pdf](reference/Projectv10.pdf), especially pp. 2-9. This file distinguishes requirements from project choices. Supplied configuration defaults do not override the brief.

## Assignment requirements

| Requirement | Source | Project consequence |
| --- | --- | --- |
| Consider the opponent's moves; do not submit a reflex-only agent | p. 2, Introduction | Implement explicit opponent lookahead |
| No libraries implementing AI, trees, graphs, etc. | p. 2, Source code | Write the algorithms ourselves; current code uses ordinary standard-library utilities |
| Run on CTI machines; language is otherwise open | p. 2 | Confirm the deployment interpreter and launch environment |
| Report algorithms and identify implementation files/functions | p. 2 | Keep descriptions tied to actual code |
| Five-minute presentation on tournament day | p. 2 | Prepare a timed demonstration and results |
| Play both species consecutively on each tournament map | p. 2 | Benchmark both sides |
| Submit source on edunao before the tournament | p. 2 | Obtain the deadline and retain the submitted version |
| Respond to each UPD within two seconds | p. 8 | Budget the entire receive/decide/send path; leave search headroom |
| Address and port appended to the launch command | p. 9 | Parse them as the final two positional arguments |

Evaluation includes AI quality, strategy, report, presentation, and tournament results. First, second, and third place receive 3, 2, and 1 bonus points. Failure to launch or communicate on tournament day caps the grade at 10/20; failure to develop an AI leads to 0 (p. 2). Reliable launch is therefore an early milestone.

## Board and winning

The board is fully observable, with `n` rows and `m` columns. Coordinates are `(x, y)` from the top-left: `0 <= x < m` and `0 <= y < n`. Each species initially occupies one cell (pp. 3, 5). Humans stay in their houses. The game ends at daylight or when one species disappears; the dominant species wins. The server may also enforce a time or ply cap (p. 8). The brief does not specify the precise tie rule.

Our representation stores resolved occupied cells and treats missing entries as empty. After combat, one cell has at most one population type. Server updates are authoritative full replacements of the listed cells, not arithmetic changes.

## Six movement rules

1. Make at least one movement each ply.
2. Move only groups belonging to our species.
3. The sum of all outgoing creatures from a source must not exceed its starting population.
4. Move exactly one cell in any of the eight directions, staying inside the board.
5. A cell cannot be both a source and a destination in the same ply. This excludes swaps and chains, regardless of packet order.
6. Each movement carries at least one creature.

These rules are on p. 3. Moving part of a population is permitted; the remainder stays. Attacking a stronger population is legal and can be strategically poor; uncertainty does not make the move invalid. Multiple sources may target one cell under the six rules, but exact combat aggregation remains an integration question.

`rules.validate_moves` enforces these rules against the pre-move board. It also conservatively enforces the p. 6 move-record/group limit by default.

## Combat

Let `A` be the attacking monsters and `D` the defending population. Apply deterministic thresholds first (pp. 3-4).

| Defender | Condition | Outcome |
| --- | --- | --- |
| Humans | `A >= D` | All humans convert; attacking population becomes `A + D` |
| Monsters | `2*A >= 3*D` | Defenders are eliminated; all attackers remain |
| Monsters | `2*D >= 3*A` | Attackers are eliminated; all defenders remain |
| Either | No applicable guarantee | Random battle |

For a random battle, the attacker win probability is `P = A/(2*D)` when `A <= D`, and `P = A/D - 0.5` when `A > D`. Thus equally sized monster groups have `P = 0.5`, while equally sized human defenders are converted deterministically before the random formula is considered.

First select the winning side. If attackers win, each attacker independently survives with probability `P`; defeated humans independently survive and convert with the same probability. If defenders win, each defender survives with probability `1-P`. A winning side can still end with zero survivors. There is no guaranteed human-defender victory at a 1.5 ratio.

For random battles, unconditional expected attacking survivors are `P^2*A`, or `P^2*(A+D)` against humans; expected defending survivors are `(1-P)^2*D`. These expectations are evaluation aids, not valid integer board transitions. `rules.sample_battle` implements an explicit sampled result with an injected random generator.

## Protocol behavior

Use a persistent TCP connection. Send NME once after connecting, receive SET/HUM/HME/MAP, and act only after UPD. The first UPD may be empty. UPD contains changes from our previous moves and the opponent's moves (pp. 5-8).

END clears game state while retaining the connection for a new game. BYE ends the connection. Detailed byte layouts are in [PROTOCOL.md](PROTOCOL.md).

## Decisions and unresolved details

| Topic | Evidence | Current decision or required check |
| --- | --- | --- |
| Turn time | Brief p. 8 says 2 seconds; config says 5 | Obey 2 seconds. Initial planned search budget around 1.5 seconds must be measured and adjusted on CTI |
| Zero moves | Rule 1 requires a movement; p. 6 MOV describes `0 <= n` | Never send an empty turn during a playable state |
| Splitting and record count | p. 3 allows partial movements and budgets multiple moves; p. 6 says record count is at most the number of groups | A partial move to one destination with creatures left behind is permitted and implemented. Default validation retains the conservative total record limit; wider splitting needs clarification or server evidence |
| Simultaneous arrivals | Multiple sources sharing a destination are not prohibited by the six rules | Verify whether the server aggregates arrivals before combat and whether move order changes results |
| Population overflow | Packet fields are single bytes, but merges/conversions can theoretically exceed 255 | The reference simulator rejects unsupported successors explicitly. Supplied maps have only 17 and 52 total creatures including humans, so cannot overflow under the brief; arbitrary-map server behavior remains unresolved |
| Victory and ties | Dominant species wins; exact ties and simultaneous extinction are unstated | A battle can leave both sides empty. Keep this distinct from a definite loss/win in analysis; check the server before assigning terminal score |
| Random-formula constant | p. 4 mentions `C` in prose but prints an explicit formula | Use the explicit formula together with p. 3's 1.5 thresholds |
| GUI setting names | p. 9 uses generic Ip/Port/Trace labels; archive uses ServerIP/ServerPort/DebugMode | Use the actual supplied config keys when preparing a working server copy |

These are engineering decisions, not additional instructor rules. Update this table when an instructor clarification or official-server observation resolves an issue.
