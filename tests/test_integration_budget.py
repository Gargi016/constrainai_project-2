"""
End-to-end integration test using the exact scenario from the project spec:

    budget <= 20000
    gpu_cost >= 14000
    ram_cost >= 8000
    storage_cost >= 2000
    gpu_cost + ram_cost + storage_cost <= budget

This walks the full pipeline: Constraint IR -> Store -> SAT/UNSAT check ->
raw unsat core -> deletion-based shrinking -> independent minimality
verification -> mapping back to source turns/text for an explanation.
"""

from constrainai.constraints import Constraint, ConstraintKind, Operator
from constrainai.expressions import var, const, add
from constrainai.store import ConstraintStore
from constrainai.solver import check_constraints, CheckResult
from constrainai.unsat_core import extract_unsat_core
from constrainai.shrink import shrink_to_subset_minimal, verify_subset_minimal


def build_store() -> ConstraintStore:
    store = ConstraintStore()
    store.add(Constraint(
        kind=ConstraintKind.BOUND, lhs=var("budget"), operator=Operator.LE, rhs=const(20000),
        source_turn=1, source_text="Budget must stay under ₹20k",
    ))
    store.add(Constraint(
        kind=ConstraintKind.BOUND, lhs=var("gpu_cost"), operator=Operator.GE, rhs=const(14000),
        source_turn=2, source_text="GPU costs at least ₹14k",
    ))
    store.add(Constraint(
        kind=ConstraintKind.BOUND, lhs=var("ram_cost"), operator=Operator.GE, rhs=const(8000),
        source_turn=3, source_text="RAM costs at least ₹8k",
    ))
    store.add(Constraint(
        kind=ConstraintKind.BOUND, lhs=var("storage_cost"), operator=Operator.GE, rhs=const(2000),
        source_turn=4, source_text="Reserve ₹2k for storage",
    ))
    store.add(Constraint(
        kind=ConstraintKind.RELATION,
        lhs=add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
        operator=Operator.LE, rhs=var("budget"),
        source_turn=5, source_text="(implicit) total component cost must fit in budget",
    ))
    return store


def test_full_pipeline_detects_unsat_and_produces_verified_minimal_core():
    store = build_store()
    active = store.active()
    assert len(active) == 5

    # 1. SAT/UNSAT check
    report = check_constraints(active)
    assert report.result == CheckResult.UNSAT

    # 2. Raw unsat core (not claimed minimal)
    raw = extract_unsat_core(active)
    assert raw is not None
    assert raw.is_unsat

    # 3. Deletion-based subset-minimal shrinking
    shrunk = shrink_to_subset_minimal(active)

    # 4. Independent verification that the returned set really is
    #    subset-minimal (re-derives it, doesn't trust the algorithm blindly).
    assert verify_subset_minimal(active, shrunk.minimal_core)

    # 5. The minimal core maps back to source turns/text for explanation.
    turns = sorted(c.source_turn for c in shrunk.minimal_core)
    assert turns == [1, 2, 3, 4, 5]  # every original statement is load-bearing here
    for c in shrunk.minimal_core:
        assert c.source_text  # provenance intact

    # 6. Sanity-check the numeric story the repair engine will later use:
    #    minimum required total is 14000+8000+2000=24000 against a 20000
    #    budget, i.e. a shortfall of exactly 4000.
    min_required = 14000 + 8000 + 2000
    budget_cap = 20000
    assert min_required - budget_cap == 4000


def test_retracting_a_constraint_resolves_the_conflict():
    store = build_store()
    # "Ignore my previous RAM requirement" -> retract the RAM lower bound.
    # find_active_on_variable matches any constraint mentioning ram_cost
    # (including the multi-variable sum constraint), so narrow to the
    # specific bound constraint we mean to retract.
    ram_constraints = [
        c for c in store.find_active_on_variable("ram_cost")
        if c.kind == ConstraintKind.BOUND
    ]
    assert len(ram_constraints) == 1
    store.retract(ram_constraints[0].id)

    active = store.active()
    assert len(active) == 4
    report = check_constraints(active)
    # Dropping ram_cost >= 8000 means ram_cost can go as low as needed
    # (even negative, in this MVP's pure-linear-arithmetic model), so the
    # remaining sum constraint becomes satisfiable.
    assert report.result == CheckResult.SAT


def test_revising_budget_upward_resolves_the_conflict():
    store = build_store()
    # "Actually increase budget to 27k" -> revise (supersede) the budget bound.
    budget_constraints = store.find_active_on_variable("budget")
    old_budget = [c for c in budget_constraints if c.operator == Operator.LE][0]

    new_budget = Constraint(
        kind=ConstraintKind.BOUND, lhs=var("budget"), operator=Operator.LE, rhs=const(27000),
        source_turn=6, source_text="Actually increase budget to ₹27k",
    )
    store.revise(old_budget.id, new_budget)

    active = store.active()
    assert len(active) == 5  # old budget bound superseded, new one active
    assert old_budget not in active

    report = check_constraints(active)
    assert report.result == CheckResult.SAT
    assert report.model["budget"] <= 27000
