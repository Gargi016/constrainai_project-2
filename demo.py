"""
Runnable end-to-end demo of the ConstrainAI deterministic reasoning core.

    python3 demo.py

Walks the exact example conversation from the spec through deterministic NL
extraction (no LLM), then the full solving pipeline:

    text -> Extractor -> ConstraintStore -> Z3 SAT/UNSAT
         -> raw unsat core -> subset-minimal shrinking (verified)
         -> solver-verified repair suggestions
         -> "Ignore my previous RAM requirement" -> retract -> SAT
"""

from constrainai.constraints import Constraint, ConstraintKind, Operator
from constrainai.expressions import var, add
from constrainai.store import ConstraintStore
from constrainai.extraction import Extractor
from constrainai.solver import check_constraints, CheckResult
from constrainai.unsat_core import extract_unsat_core
from constrainai.shrink import shrink_to_subset_minimal, verify_subset_minimal
from constrainai.repair import suggest_repairs


def main() -> None:
    store = ConstraintStore()
    extractor = Extractor()

    conversation = [
        "Budget must stay under ₹20k",
        "GPU costs at least ₹14k",
        "RAM costs at least ₹8k",
        "Reserve ₹2k for storage",
    ]

    print("=== Turn-by-turn NL extraction (deterministic, no LLM) ===")
    for i, text in enumerate(conversation, start=1):
        outcome = extractor.process_turn(text, i, store)
        print(f'  turn {i}: "{text}"')
        print(f"    -> {outcome.kind.value}: {outcome.message}")

    # The cross-variable "fits in budget" relation isn't expressible by
    # this MVP's bound-only NL patterns (it's a RELATION, not a BOUND), so
    # it's added directly here -- extraction and the relation layer are
    # separate, composable modules per the spec.
    relation = Constraint(
        kind=ConstraintKind.RELATION,
        lhs=add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
        operator=Operator.LE, rhs=var("budget"),
        source_turn=5, source_text="(implicit) gpu + ram + storage <= budget",
    )
    store.add(relation)
    print('  turn 5: "(implicit) gpu + ram + storage <= budget" -> added directly (cross-variable relation)')

    print("\n=== SAT/UNSAT check ===")
    active = store.active()
    report = check_constraints(active)
    print(f"Result: {report.result.value.upper()}")

    if report.result == CheckResult.UNSAT:
        raw = extract_unsat_core(active)
        print(f"\nRaw unsat core (NOT claimed minimal), {len(raw.raw_core)} constraint(s):")
        for c in raw.raw_core:
            print(f"  {c.describe()}")

        shrunk = shrink_to_subset_minimal(active)
        verified = verify_subset_minimal(active, shrunk.minimal_core)
        print(f"\nSubset-minimal core (verified={verified}), "
              f"{len(shrunk.minimal_core)} constraint(s), {shrunk.solver_calls} solver calls:")
        for c in shrunk.minimal_core:
            print(f"  {c.describe()}")

        print("\n=== Solver-verified repair suggestions ===")
        repairs = suggest_repairs(shrunk.minimal_core, full_active_set=active)
        for r in repairs:
            print(f"  - {r.describe()}")

    print("\n=== 'Ignore my previous RAM requirement' -> retract ===")
    outcome = extractor.process_turn("Ignore my previous RAM requirement", 6, store)
    print(f"  -> {outcome.kind.value}: {outcome.message}")
    report2 = check_constraints(store.active())
    print(f"Result after retraction: {report2.result.value.upper()}")
    if report2.result == CheckResult.SAT:
        print(f"Example satisfying model: {report2.model}")


if __name__ == "__main__":
    main()
