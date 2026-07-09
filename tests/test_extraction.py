import pytest

from constrainai.constraints import ConstraintKind, Operator, ConstraintStatus
from constrainai.extraction import Extractor, OutcomeKind
from constrainai.store import ConstraintStore
from constrainai.solver import check_constraints, CheckResult


def test_add_le_bound_under_phrase():
    store = ConstraintStore()
    outcome = Extractor().process_turn("Budget must stay under ₹20k", 1, store)
    assert outcome.kind == OutcomeKind.ADD
    c = outcome.constraint
    assert c.lhs.name == "budget"
    assert c.operator == Operator.LE
    assert c.rhs.value == 20000
    assert c.source_turn == 1
    assert c.source_text == "Budget must stay under ₹20k"
    assert store.active() == [c]


def test_add_ge_bound_at_least_phrase():
    store = ConstraintStore()
    outcome = Extractor().process_turn("GPU costs at least ₹14k", 2, store)
    assert outcome.kind == OutcomeKind.ADD
    c = outcome.constraint
    assert c.lhs.name == "gpu_cost"
    assert c.operator == Operator.GE
    assert c.rhs.value == 14000


def test_add_ge_bound_reserve_phrase():
    store = ConstraintStore()
    outcome = Extractor().process_turn("Reserve ₹2k for storage", 4, store)
    assert outcome.kind == OutcomeKind.ADD
    c = outcome.constraint
    assert c.lhs.name == "storage_cost"
    assert c.operator == Operator.GE
    assert c.rhs.value == 2000


def test_number_parsing_variants():
    store = ConstraintStore()
    o1 = Extractor().process_turn("Budget must stay under 20,000", 1, store)
    assert o1.constraint.rhs.value == 20000

    o2 = Extractor().process_turn("GPU costs at least 1.5 lakh", 2, store)
    assert o2.constraint.rhs.value == 150000


def test_unrecognized_phrase_leaves_store_untouched():
    store = ConstraintStore()
    outcome = Extractor().process_turn("The weather is nice today", 1, store)
    assert outcome.kind == OutcomeKind.UNRECOGNIZED
    assert store.all() == []


def test_retraction_of_existing_requirement():
    store = ConstraintStore()
    Extractor().process_turn("RAM costs at least ₹8k", 3, store)
    ram_id = store.active()[0].id

    outcome = Extractor().process_turn("Ignore my previous RAM requirement", 6, store)
    assert outcome.kind == OutcomeKind.RETRACT
    assert outcome.old_constraint_id == ram_id
    assert store.get(ram_id).status == ConstraintStatus.RETRACTED
    assert store.active() == []


def test_retraction_with_no_matching_active_constraint_is_ambiguous():
    store = ConstraintStore()
    outcome = Extractor().process_turn("Ignore my previous RAM requirement", 1, store)
    assert outcome.kind == OutcomeKind.AMBIGUOUS
    assert store.all() == []  # nothing mutated


def test_revision_increases_budget():
    store = ConstraintStore()
    Extractor().process_turn("Budget must stay under ₹20k", 1, store)
    old_id = store.active()[0].id

    outcome = Extractor().process_turn("Actually increase budget to ₹27k", 5, store)
    assert outcome.kind == OutcomeKind.REVISE
    assert outcome.old_constraint_id == old_id
    assert store.get(old_id).status == ConstraintStatus.SUPERSEDED

    new_c = outcome.constraint
    assert new_c.operator == Operator.LE  # reuses the prior direction
    assert new_c.rhs.value == 27000
    assert store.active() == [new_c]


def test_revision_with_no_prior_constraint_is_ambiguous():
    store = ConstraintStore()
    outcome = Extractor().process_turn("Actually increase budget to ₹27k", 1, store)
    assert outcome.kind == OutcomeKind.AMBIGUOUS
    assert store.all() == []


def test_revision_with_multiple_active_matches_is_ambiguous():
    store = ConstraintStore()
    ext = Extractor()
    ext.process_turn("Budget must stay under ₹20k", 1, store)
    # A second, independent active bound on the same variable (contrived,
    # but demonstrates the store correctly refuses to silently pick one).
    ext.process_turn("Budget must stay under ₹18k", 2, store)
    assert len(store.active()) == 2

    outcome = ext.process_turn("Actually increase budget to ₹27k", 3, store)
    assert outcome.kind == OutcomeKind.AMBIGUOUS
    # Nothing should have been superseded since we couldn't disambiguate.
    assert len(store.active()) == 2


def test_full_spec_conversation_end_to_end():
    """
    Runs the exact 6-turn conversation from the spec through the extractor
    and confirms: constraints extracted correctly, UNSAT detected after
    turn 5's implicit relation is added, and turns 5/6-style resolution
    (revise budget upward, retract RAM) each independently restore SAT.
    """
    from constrainai.constraints import Constraint
    from constrainai.expressions import var, add

    store = ConstraintStore()
    ext = Extractor()

    turns = [
        "Budget must stay under ₹20k",
        "GPU costs at least ₹14k",
        "RAM costs at least ₹8k",
        "Reserve ₹2k for storage",
    ]
    for i, text in enumerate(turns, start=1):
        outcome = ext.process_turn(text, i, store)
        assert outcome.kind == OutcomeKind.ADD, f"turn {i} failed: {outcome.message}"

    # The implicit sum<=budget relation isn't NL-extractable from this
    # MVP's bound-only patterns (it's a cross-variable RELATION), so it's
    # added directly, exactly as in demo.py -- extraction and the relation
    # layer are independent concerns per the spec's module boundaries.
    store.add(Constraint(
        kind=ConstraintKind.RELATION,
        lhs=add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
        operator=Operator.LE, rhs=var("budget"),
        source_turn=5, source_text="(implicit) gpu + ram + storage <= budget",
    ))

    assert check_constraints(store.active()).result == CheckResult.UNSAT

    # Path A: retract RAM requirement.
    store_a = _clone_active_into_new_store(store)
    outcome_a = ext.process_turn("Ignore my previous RAM requirement", 6, store_a)
    assert outcome_a.kind == OutcomeKind.RETRACT
    assert check_constraints(store_a.active()).result == CheckResult.SAT

    # Path B: revise budget upward instead.
    store_b = _clone_active_into_new_store(store)
    outcome_b = ext.process_turn("Actually increase budget to ₹27k", 6, store_b)
    assert outcome_b.kind == OutcomeKind.REVISE
    assert check_constraints(store_b.active()).result == CheckResult.SAT


def _clone_active_into_new_store(store: ConstraintStore) -> ConstraintStore:
    """Test helper: copy the currently-active constraints into a fresh store
    (so two alternative resolutions can be explored independently)."""
    new_store = ConstraintStore()
    for c in store.active():
        new_store.add(c.model_copy(deep=True))
    return new_store


def test_relation_extraction_after_phrase():
    store = ConstraintStore()
    outcome = Extractor().process_turn(
        "Project B must start after Project A ends", 1, store
    )
    assert outcome.kind == OutcomeKind.ADD
    c = outcome.constraint
    assert c.kind == ConstraintKind.RELATION
    assert c.lhs.name == "project_b_start"
    assert c.operator == Operator.GE
    assert c.rhs.name == "project_a_end"


def test_relation_extraction_before_phrase():
    store = ConstraintStore()
    outcome = Extractor().process_turn(
        "Project A must finish before Project B starts", 1, store
    )
    assert outcome.kind == OutcomeKind.ADD
    c = outcome.constraint
    assert c.kind == ConstraintKind.RELATION
    assert c.lhs.name == "project_a_end"
    assert c.operator == Operator.LE
    assert c.rhs.name == "project_b_start"


def test_relation_extraction_unresolvable_variables_is_unrecognized():
    store = ConstraintStore()
    outcome = Extractor().process_turn(
        "The meeting is after lunch", 1, store
    )
    assert outcome.kind == OutcomeKind.UNRECOGNIZED
    assert store.all() == []


def test_relation_does_not_shadow_bound_addition():
    # No "after"/"before" keyword -> falls through to normal bound handling.
    store = ConstraintStore()
    outcome = Extractor().process_turn("Budget must stay under ₹20k", 1, store)
    assert outcome.kind == OutcomeKind.ADD
    assert outcome.constraint.kind == ConstraintKind.BOUND
