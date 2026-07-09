# ConstrainAI Evaluation Report

## Extraction metrics

| Metric | Value |
|---|---|
| Turns evaluated | 23 |
| Per-turn kind accuracy | 100.0% |
| Extraction precision | 100.0% |
| Extraction recall | 100.0% |
| Revision/retraction accuracy | 100.0% |

## Conflict / repair metrics

| Metric | Value |
|---|---|
| Cases evaluated | 6 |
| SAT/UNSAT accuracy | 100.0% |
| Exact conflict-set match rate | 100.0% |
| Conflict precision (avg) | 100.0% |
| Conflict recall (avg) | 100.0% |
| Avg core-shrinking solver calls | 5.0 |
| Repair validity rate | 100.0% |

## Solver latency vs constraint count

| N constraints | Time (ms) |
|---|---|
| 10 | 1.70 |
| 50 | 6.42 |
| 100 | 12.46 |
| 250 | 29.07 |
| 500 | 57.31 |

## Per-case detail: extraction

| Case | Turn | Domain | Text | Expected | Actual | Match |
|---|---|---|---|---|---|---|
| budgeting_basic_additions | 1 | budgeting | Budget must stay under ₹20k | add | add | ✅ |
| budgeting_basic_additions | 2 | budgeting | GPU costs at least ₹14k | add | add | ✅ |
| budgeting_basic_additions | 3 | budgeting | RAM costs at least ₹8k | add | add | ✅ |
| budgeting_basic_additions | 4 | budgeting | Reserve ₹2k for storage | add | add | ✅ |
| budgeting_revise_then_retract | 1 | budgeting | Budget must stay under ₹20k | add | add | ✅ |
| budgeting_revise_then_retract | 2 | budgeting | RAM costs at least ₹8k | add | add | ✅ |
| budgeting_revise_then_retract | 3 | budgeting | Actually increase budget to ₹27k | revise | revise | ✅ |
| budgeting_revise_then_retract | 4 | budgeting | Ignore my previous RAM requirement | retract | retract | ✅ |
| budgeting_number_formats | 1 | budgeting | Budget must stay under 20,000 | add | add | ✅ |
| budgeting_number_formats | 2 | budgeting | GPU costs at least 1.5 lakh | add | add | ✅ |
| budgeting_revise_without_prior_is_ambiguous | 1 | budgeting | Actually increase budget to ₹27k | ambiguous | ambiguous | ✅ |
| budgeting_retract_without_prior_is_ambiguous | 1 | budgeting | Ignore my previous RAM requirement | ambiguous | ambiguous | ✅ |
| budgeting_unrecognized_smalltalk | 1 | budgeting | Thanks, that's helpful! | unrecognized | unrecognized | ✅ |
| hardware_basic_additions | 1 | hardware | GPU costs at least ₹10k | add | add | ✅ |
| hardware_basic_additions | 2 | hardware | RAM costs at least ₹4k | add | add | ✅ |
| hardware_basic_additions | 3 | hardware | Budget must stay under ₹15k | add | add | ✅ |
| hardware_revise_gpu_requirement | 1 | hardware | GPU costs at least ₹10k | add | add | ✅ |
| hardware_revise_gpu_requirement | 2 | hardware | Actually decrease GPU to ₹9k | revise | revise | ✅ |
| scheduling_after_relation | 1 | scheduling | Project B must start after Project A ends | add | add | ✅ |
| scheduling_before_relation | 1 | scheduling | Project A must finish before Project B starts | add | add | ✅ |
| scheduling_mixed_bound_and_relation | 1 | scheduling | Project A end must stay under 10 | add | add | ✅ |
| scheduling_mixed_bound_and_relation | 2 | scheduling | Project B must start after Project A ends | add | add | ✅ |
| scheduling_unresolvable_relation_is_unrecognized | 1 | scheduling | The party starts after the concert | unrecognized | unrecognized | ✅ |

## Per-case detail: conflict

| Case | Domain | Expected | Actual | Exact match | Precision | Recall | Repairs | Verified |
|---|---|---|---|---|---|---|---|---|
| budgeting_spec_conflict | budgeting | unsat | unsat | True | 1.00 | 1.00 | 4 | True |
| budgeting_satisfiable | budgeting | sat | sat | — | — | — | 0 | — |
| hardware_conflict | hardware | unsat | unsat | True | 1.00 | 1.00 | 3 | True |
| hardware_satisfiable | hardware | sat | sat | — | — | — | 0 | — |
| scheduling_conflict | scheduling | unsat | unsat | True | 1.00 | 1.00 | 2 | True |
| scheduling_satisfiable | scheduling | sat | sat | — | — | — | 0 | — |