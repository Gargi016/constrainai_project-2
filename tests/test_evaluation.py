from evaluation.runner import (
    run_extraction_cases,
    run_conflict_cases,
    benchmark_solver_latency,
    format_console_report,
    format_markdown_report,
    run_all,
)


def test_extraction_cases_all_pass():
    metrics = run_extraction_cases()
    assert metrics.total_turns > 0
    assert metrics.kind_accuracy == 1.0, [
        r for r in metrics.results if not r.kind_correct
    ]
    assert metrics.extraction_precision == 1.0
    assert metrics.extraction_recall == 1.0
    assert metrics.revision_retraction_accuracy == 1.0


def test_conflict_cases_all_pass():
    metrics = run_conflict_cases()
    assert metrics.total_cases > 0
    assert metrics.sat_unsat_accuracy == 1.0, [
        r for r in metrics.results if not r.sat_unsat_correct
    ]
    assert metrics.exact_conflict_match_rate == 1.0
    assert metrics.avg_conflict_precision == 1.0
    assert metrics.avg_conflict_recall == 1.0
    assert metrics.repair_validity_rate == 1.0
    # Sanity: every UNSAT case in our fixed set is a 3-5 constraint example,
    # so deletion-based shrinking should never need more than ~6 solver calls.
    assert metrics.avg_shrink_solver_calls <= 6


def test_latency_benchmark_runs_and_scales_sanely():
    bench = benchmark_solver_latency(sizes=[5, 20, 50])
    assert len(bench.times_seconds) == 3
    assert all(t >= 0 for t in bench.times_seconds)
    # Not a strict performance assertion (timing is noisy in CI), just a
    # sanity check that solving 50 trivial constraints doesn't take long.
    assert bench.times_seconds[-1] < 2.0


def test_report_formatters_produce_nonempty_output():
    report = run_all()
    console = format_console_report(report)
    markdown = format_markdown_report(report)
    assert "Extraction metrics" in console
    assert "# ConstrainAI Evaluation Report" in markdown
    assert "budgeting_spec_conflict" in markdown
