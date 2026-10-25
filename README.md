# Reactive satellite covering

Exact continuous-time partial booking, full-pass MILP, validated plans,
measured comparisons on all three datasets, notebook and standalone slides.
Original input files and starter notebook are preserved.

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python solution.py data/data12.json --output mySolution.json
python solution.py data/data2.json --budget 5000 --priorities --limit 110
python experiment.py
jupyter lab solution.ipynb
```
Install Jupyter separately. `--full` selects whole passes. The default is
SciPy/HiGHS; optional `--backend docplex` requires docplex and licensed CPLEX
and is untested here. One deadline covers model preparation and every objective
stage; maximum 120s. Shutdown/validation can add small overhead.

## Model
For pass length L, binary booking x, local endpoints s,e and access witness z:
```
0 <= s,e <= L*x; e-s >= d*x; z <= x
s + (L-u+d)*z - L*x <= 0
e - (l+d)*z >= 0
```
[l,u] is clipped feasible visibility. This enforces d-duration overlap and one
contiguous booking per pass, with no time grid. Cost: fixed*x + rate*(e-s).
Without a budget, minimize cost covering every reachable request; report the
unreachable ones separately. With a budget, maximize coverage then minimize cost;
priorities retain proven P1, then P2, P3 counts before cost. Stop on an unproven
stage. Identical supports are aggregated with priority multiplicities; continuous
coverage variables are exact because uncovered supports force zero and covered
supports can reach one. Subset cover rows imply supersets. Validated complete
incumbents provide safe cost cutoffs. Independent evaluation uses actual overlaps.

## Evidence
See RESULTS.md and results/summary.csv. experiment.py reproduces 36 quick runs
(12s main, 3s budget). Short seeded runtime excludes seed discovery. No claim of
partial optimality or a complete Pareto frontier is made. Recommended intervals
are [passId,start,end] triples in results/intervals.json; the notebook reconstructs
standard Bookings JSON and audits every plan. results/seeds.json preserves the
previous data12 incumbent; the archive also includes full plan reports.

Costs use the supplied fixed=120, rate=1/s, minimum visibility=30s. The finite
request lists do not prove coverage at unmodeled event times. This is a one-event
reservation problem, not a simultaneous acquisition schedule. Respect the ONERA
PDF's proprietary notice; the document is not reproduced here.
