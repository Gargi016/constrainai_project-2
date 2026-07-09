"""
Evaluation harness for ConstrainAI.

Two independent case sets, matching the metrics listed in the spec:

- `extraction_cases.py` -- mini-conversations (a few turns each) run through
  the deterministic Extractor, scored per turn against an expected outcome
  kind and, for ADD/REVISE turns, an expected constraint signature. Used to
  compute extraction precision/recall and revision/retraction accuracy.

- `conflict_cases.py` -- directly-constructed constraint sets (bypassing NL,
  since these test the solving pipeline in isolation) with known expected
  SAT/UNSAT status and, for UNSAT cases, the expected exact subset-minimal
  conflict set. Used to compute SAT/UNSAT accuracy, exact conflict-set
  match rate, conflict precision/recall, core-shrinking cost (solver
  calls), and repair validity.

`runner.py` also includes a solver-latency-vs-constraint-count benchmark
(independent of both case sets, since latency scaling is a property of the
solver/compiler, not of any particular conversation).

Run `python3 -m evaluation.runner` for a console report.
"""
