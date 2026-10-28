"""Exact window selection and renderer-only localization acceptance checks."""

import copy
from fractions import Fraction
import math
import random
import unittest

from bci_regression import EvaluationSet, PredictionSet, compare
from bci_regression.report import _localization_window, render_report
from test_report import _Document


def _samples(baseline, candidate):
    return [dict(baseline_error=b, candidate_error=c)
            for b, c in zip(baseline, candidate)]


def _oracle(samples):
    """Independent exhaustive calculation, with no rolling accumulator."""
    width = min(24, len(samples))
    if not width:
        return None
    scores = [sum((Fraction.from_float(float(row["candidate_error"])) ** 2
                   - Fraction.from_float(float(row["baseline_error"])) ** 2
                   for row in samples[start:start + width]), Fraction())
              for start in range(len(samples) - width + 1)]
    maximum = max(scores)
    if maximum <= 0:
        return None
    start = scores.index(maximum)
    return start, start + width


def _comparison(*, burst_error=12.0, omit_candidate=None, hostile=""):
    """A known late burst, independently of any localization implementation."""
    targets, baseline, candidate = [], [], []
    for index in range(600):
        sample = f"sample-{index:04d}" + (hostile if index in (480, 503) else "")
        targets.append(dict(session_id="late-session", sample_id=sample,
                            timestamp=index * 2.0, target_vx=0.0, target_vy=0.0))
        baseline.append(dict(session_id="late-session", sample_id=sample,
                             predicted_vx=2.0, predicted_vy=0.0))
        if index != omit_candidate:
            error = burst_error if 480 <= index < 504 else 1.0
            candidate.append(dict(session_id="late-session", sample_id=sample,
                                  predicted_vx=error, predicted_vy=0.0))
    evaluation = EvaluationSet.from_records(targets, evaluation_id="late-burst-acceptance",
        units="synthetic velocity units", coordinates="synthetic-x-y",
        purpose="constructed localization acceptance; no decoder performance claim")
    baseline = PredictionSet.from_records(baseline, run_id="baseline", evaluation=evaluation)
    candidate = PredictionSet.from_records(candidate, run_id="candidate", evaluation=evaluation)
    return compare(evaluation, baseline, candidate, tolerance=0.1)


def _within(node, ancestor):
    while node is not None:
        if node is ancestor:
            return True
        node = node.parent
    return False


class LocalizationSelectionTests(unittest.TestCase):
    def test_known_late_regression_is_localized_beyond_first_preview(self):
        result = _comparison()
        self.assertTrue(result["sessions"][0]["regression"])
        self.assertTrue(all(row["candidate_error"] < row["baseline_error"]
                            for row in result["samples"][:24]))
        self.assertEqual(_oracle(result["samples"]), (480, 504))
        self.assertEqual(_localization_window(result["samples"]), (480, 504))

    def test_matches_independent_exhaustive_oracle(self):
        generator = random.Random(20261028)
        for size in (1, 7, 23, 24, 25, 49, 80, 123):
            for trial in range(5):
                samples = _samples([generator.randrange(0, 33) / 4 for _ in range(size)],
                                   [generator.randrange(0, 33) / 4 for _ in range(size)])
                with self.subTest(size=size, trial=trial):
                    self.assertEqual(_localization_window(samples), _oracle(samples))

    def test_empty_equal_and_everywhere_improved_have_no_added_error_window(self):
        for samples in ([], _samples([2] * 70, [2] * 70),
                        _samples([2] * 70, [1] * 70), _samples([0], [0])):
            with self.subTest(count=len(samples)):
                self.assertIsNone(_localization_window(samples))

    def test_positive_sample_does_not_override_nonpositive_window_sum(self):
        candidate = [0.0] * 48
        candidate[35] = 2.0
        samples = _samples([1.0] * 48, candidate)
        self.assertGreater(candidate[35], 1.0)
        self.assertIsNone(_oracle(samples))
        self.assertIsNone(_localization_window(samples))

    def test_short_session_uses_all_available_samples(self):
        for size in (1, 3, 23, 24):
            with self.subTest(size=size):
                self.assertEqual(_localization_window(_samples([1] * size, [2] * size)),
                                 (0, size))

    def test_fixed_window_includes_last_sample(self):
        candidate = [1] * 600
        candidate[-24:] = [12] * 24
        self.assertEqual(_localization_window(_samples([2] * 600, candidate)), (576, 600))

    def test_ties_choose_earliest_window(self):
        self.assertEqual(_localization_window(_samples([1] * 60, [2] * 60)), (0, 24))
        candidate = [1] * 120
        candidate[10:34] = [12] * 24
        candidate[80:104] = [12] * 24
        self.assertEqual(_localization_window(_samples([2] * 120, candidate)), (10, 34))

    def test_rank_uses_squared_error_difference_not_difference_of_errors(self):
        samples = _samples([0] * 24 + [9] * 24, [2] * 24 + [10] * 24)
        self.assertEqual(_localization_window(samples), (24, 48))
        self.assertEqual(_localization_window(samples), _oracle(samples))

    def test_overflow_underflow_and_neighboring_floats_match_exact_oracle(self):
        for scale in (math.ulp(0.0), math.ldexp(1.0, -500), 1.0,
                      math.ldexp(1.0, 500), 1e308):
            lower = math.nextafter(scale, 0.0)
            higher = math.nextafter(scale, math.inf)
            samples = _samples([scale] * 72,
                               [lower] * 24 + [higher] * 24 + [scale] * 24)
            with self.subTest(scale=scale):
                self.assertEqual(_localization_window(samples), (24, 48))
                self.assertEqual(_localization_window(samples), _oracle(samples))

    def test_cancellation_between_huge_and_tiny_contributions_is_exact(self):
        # The first whole-session window cancels the huge positive/negative
        # contributions exactly, leaving a strictly positive subnormal square.
        samples = _samples([0.0, 1e308, 0.0], [1e308, 0.0, math.ulp(0.0)])
        self.assertEqual(_oracle(samples), (0, 3))
        self.assertEqual(_localization_window(samples), (0, 3))

    def test_malformed_errors_do_not_create_a_localization(self):
        for field in ("baseline_error", "candidate_error"):
            for invalid in (None, True, -1.0, float("nan"), float("inf"), "bad"):
                samples = _samples([1] * 50, [2] * 50)
                samples[32][field] = invalid
                with self.subTest(field=field, invalid=invalid):
                    self.assertIsNone(_localization_window(samples))

    def test_selection_does_not_mutate_samples(self):
        samples = _samples([1] * 49, [2] * 49)
        original = copy.deepcopy(samples)
        self.assertEqual(_localization_window(samples), (0, 24))
        self.assertEqual(samples, original)


class LocalizationReportTests(unittest.TestCase):
    def test_selected_session_contains_exact_late_references_and_window_samples(self):
        result = _comparison()
        original = copy.deepcopy(result)
        document = _Document(render_report(result))
        panel = document.one(tag="section", cls="session-detail")
        window = document.one(tag="section", cls="localization")
        self.assertTrue(_within(window, panel))
        self.assertEqual(window.attrs["data-localization-start"], "480")
        self.assertEqual(window.attrs["data-localization-stop"], "504")
        references = document.one(cls="window-references")
        for expected in ("sample-0480", "sample-0503", "960", "1006"):
            self.assertIn(expected, references.text)
        table = document.one(tag="table", cls="sample-table")
        row_ids = [node.text for node in document.find(tag="th")
                   if node.attrs.get("scope") == "row" and _within(node, table)]
        self.assertEqual(row_ids, [f"sample-{index:04d}" for index in range(480, 504)])
        self.assertEqual(len(document.find(tag="details", cls="full-session-trace")), 1)
        self.assertIn("Highest added-error window", window.text)
        self.assertEqual(result, original)

    def test_overall_improvement_can_have_local_added_error_without_new_regression_flag(self):
        result = _comparison(burst_error=4.0)
        original = copy.deepcopy(result)
        self.assertLess(result["sessions"][0]["delta"], 0)
        self.assertFalse(result["sessions"][0]["regression"])
        document = _Document(render_report(result))
        window = document.one(tag="section", cls="localization")
        self.assertEqual(window.attrs["data-localization-start"], "480")
        self.assertIn("Lower RMSE in the session", document.root.text)
        self.assertIn("This session improves overall", window.text)
        self.assertEqual(result, original)

    def test_scored_sample_window_retains_timestamp_gaps_without_inventing_duration(self):
        result = _comparison()
        for index, row in enumerate(result["samples"]):
            if index >= 492:
                row["timestamp"] += 100_000
        document = _Document(render_report(result))
        window = document.one(tag="section", cls="localization")
        self.assertEqual(window.attrs["data-localization-start"], "480")
        self.assertEqual(window.attrs["data-localization-stop"], "504")
        references = document.one(cls="window-references")
        self.assertIn("960.0", references.text)
        self.assertIn("101006.0", references.text)
        self.assertIn("consecutive scored samples", window.text)
        self.assertIn("may span recording gaps", window.text)
        self.assertIn("not a fixed-duration window", window.text)

    def test_invalid_session_has_no_window_or_paired_trace(self):
        result = _comparison(omit_candidate=500)
        self.assertFalse(result["complete"])
        self.assertEqual(result["sessions"][0]["status"], "invalid")
        document = _Document(render_report(result))
        self.assertFalse(document.find(tag="section", cls="localization"))
        self.assertFalse(document.find(tag="svg"))
        self.assertIn("Incomplete comparison", document.root.text)

    def test_no_positive_window_is_explicit_and_does_not_invent_a_region(self):
        result = _comparison(burst_error=1.0)
        document = _Document(render_report(result))
        self.assertFalse(document.find(tag="section", cls="localization"))
        empty = document.one(tag="section", cls="localization-empty")
        self.assertIn("No added-error window", empty.text)

    def test_hostile_selected_ids_and_timestamps_remain_text(self):
        attack = '\"><img src=x onerror="alert(1)"><script>fetch("evil")</script>&'
        result = _comparison(hostile=attack)
        result["samples"][480]["timestamp"] = attack
        original = copy.deepcopy(result)
        document = _Document(render_report(result))
        references = document.one(cls="window-references")
        self.assertIn(attack, references.text)
        self.assertFalse(document.find(tag="img"))
        self.assertEqual(len(document.find(tag="script")), 1)
        script = document.one(tag="script", id="report-interaction")
        self.assertNotIn(attack, script.text)
        for node in document.nodes:
            self.assertFalse(any(key.startswith("on") for key in node.attrs))
        self.assertEqual(result, original)


if __name__ == "__main__":
    unittest.main()
