# Measured results

| Dataset | Full optimum | Partial incumbent | Covered | Cost reduction | Partial status |
|---|---:|---:|---:|---:|---|
| data12 | 1525 | 1220 | 225 | 20.0% | feasible_not_proven |
| data4 | 9991 | 7584 | 2234 | 24.09% | feasible_not_proven |
| data2 | 16847 | 10914 | 6867 | 35.22% | feasible_not_proven |

All recommended plans independently validate and cover every supplied request. Full-pass costs are proven optimal; partial costs are feasible upper bounds, not proven optima.

- data12: partial cost 1220; no fresh bound returned in the quick seeded run.
- data4: partial cost 7584; cost lower bound 5730.972894; solver gap 24.433%.
- data2: partial cost 10914; cost lower bound 10820.726984; solver gap 0.855%.

## Protocol and limitations
45 tests passed. Main quick solves use 12s, budget samples 3s; all stages share
the deadline. Partial models use the previous data12 seed or a trimmed full
solution. Their timing excludes seed discovery. The earlier 110s data12 run
found cost 1,220 with lower bound 874.524634 and 28.317653% gap, not an optimum.
Three random-order seeds include redundancy deletion; deterministic greedy runs
once. Cost comparisons hold coverage fixed. Six budget samples use full passes
and lexicographic priorities, not the unweighted objective or a complete frontier.
Stage bounds can refer to negative coverage rather than cost; see bound_stage.
Optional DOCPLEX support is untested. All input requests are reachable.

## Input SHA-256 and environment
- data12: `91bb0f507a14035da7385eb49300b991329cecc7aacd4b478de71eadc49e9996`
- data4: `b84a318130651378b46fe06d874921ede5d252a2d4cc157e7d901ac989974d62`
- data2: `461c5deea9e8e3ff1e76ec45eff4226ba51cb9164dbf633311bc3251f9620b54`

{
  "python": "3.12.8",
  "scipy": "1.13.1",
  "platform": "Linux-6.1.155+-x86_64-with-glibc2.43"
}
