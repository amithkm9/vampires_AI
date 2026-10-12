# Search allocation and resource-control upgrade

Scoped literature review, 2026-10-12. Question: which ideas address expensive stochastic roots and combinatorial group movements under this project's two-second turn deadline? Inclusion: original papers with applicable mechanisms. This is a targeted comparison, not an exhaustive or systematic review. Exact queries and screening decisions are in `notes/search-log.csv`; verified source details are in `notes/literature-matrix.csv` and `references.bib`.

## What transfers, and what does not

Churchill and Buro's portfolio greedy search restricts each unit to script proposals and improves script assignments through local search and opponent responses. Section V/Algorithm 2 motivates our diverse capture, attack, merge and escape proposals. Our implementation is a candidate portfolio inside expectiminimax: it does **not** reproduce their hill climbing or StarCraft playout system. Their combat simulation differs from this game's chance battles and movement rules. No published strength result is transferred. [Original paper](https://skatgame.net/mburo/ps/combat13.pdf).

Lanctot et al. define sparse-sampled expectiminimax by drawing chance outcomes with replacement and averaging them equally (Section 3.1). Their bound propagation and finite-depth formulation support retaining exact interval bookkeeping here. Our current scheduler enumerates outcomes and keeps unvisited probability mass; it is **not** their sampled MCMS implementation. Sparse sampling remains a separate future challenger, requiring explicit seeds and approximate-value labels. [Original paper](https://www.ijcai.org/Proceedings/13/Papers/093.pdf).

Kaufmann and Koolen propagate confidence intervals through fixed max/min trees to select a root arm (Sections 1–2). Their assumptions include independent stochastic leaf oracles. This supports treating root choice as the objective, but does not justify statistical confidence claims for our selective chance tree. Our root scheduler uses deterministic interval bounds and round-robin continuations; it does **not** implement their BAI algorithm or inherit its sample-complexity guarantees. [Original paper](https://proceedings.neurips.cc/paper_files/paper/2017/file/a6d259bfbfa2062843ef543e21d7ec8e-Paper.pdf).

## Implemented hypotheses

1. `balanced.choose_balanced`: suspend recursive work after a leaf update or generation call, share turns across roots, stop roots whose upper bound is below another root's lower bound, preserve completed shallower decisions. This addresses root starvation but adds scheduler overhead; equality to exact retained-tree values does not establish stronger play under a deadline.
2. `strategy.evaluate_resources`: allocate currently affordable houses exclusively by arrival ply, discount distance slowly, and value projected population nonlinearly. This can recognize that a present lead gives way to a resource deficit. It still ignores route interference, interception, future growth and unknown daylight timing; it is not a win probability.
3. `strategy.portfolio_turns`: blend baseline candidates with independently validated policy proposals. Keep shared contested destinations excluded. Diversity can displace useful partial moves, so measure it as a separate ablation.

Avoid assuming that changing algorithms automatically improves strength. The benchmark compares each feature separately against the immutable pushed engine, then evaluates a locked candidate on fresh maps/seeds at the normal budget. See [experiment protocol and retained negative results](../experiments/2026-10-12-upgrade/EXPERIMENT.md).

## Remaining hard problems

Opponent identification from protocol updates is ambiguous: an update may include stochastic consequences and does not expose a clean opponent policy label. Continue searching strong legal replies for either species. Do not claim that the client recognizes individual opponents or learns their style. Later adaptation requires validated action reconstruction and evidence across diverse opponents.

Resource paths and unavoidable endgame risks need deeper work than a leaf bonus. Shared-target battle semantics, official-server parity and CTI timing must be resolved before tournament claims. No algorithm can guarantee a win in every stochastic position.
