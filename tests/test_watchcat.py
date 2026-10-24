import unittest

from qpet.demo import fake_run
from qpet.watchcat import analyze_run, compare_runs, recommend_run


class WatchcatTests(unittest.TestCase):
    def test_edge_population_creates_warning(self):
        report = analyze_run(fake_run("small", 16, 4, error=0.2, runtime=0.3))
        self.assertEqual(report.pet_state, "worried")
        self.assertEqual(report.status, "needs_review")
        self.assertTrue(any(item.code == "MEMORY_EDGE_POPULATION" for item in report.diagnostics))

    def test_convergence_comparison_rejects_bad_candidate(self):
        reference = fake_run("reference", 48, 12, error=0.00001, runtime=4.0)
        bad = fake_run("bad", 16, 4, error=0.2, runtime=0.3)
        comparison = compare_runs(bad, reference, observables=["n_memory"], abs_tolerance=0.001)
        self.assertFalse(comparison.passed)

    def test_recommends_cheapest_passing_candidate(self):
        reference = fake_run("reference", 48, 12, error=0.00001, runtime=4.0)
        candidates = [
            fake_run("bad", 16, 4, error=0.2, runtime=0.3),
            fake_run("good", 24, 8, error=0.0002, runtime=0.8),
        ]
        selected, comparisons = recommend_run(
            candidates,
            reference,
            observables=["n_memory", "n_buffer"],
            abs_tolerance=0.001,
            relative_tolerance=0.01,
        )
        self.assertEqual(selected.label, "good")
        self.assertEqual(len(comparisons), 2)


if __name__ == "__main__":
    unittest.main()
