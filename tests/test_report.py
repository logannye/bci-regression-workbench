"""Behavior and unsafe-text checks for the portable report."""

import copy
from html.parser import HTMLParser
import unittest

from bci_regression.report import render_report


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def _result():
    return {
        "schema_version": "1",
        "description": "Synthetic fixture. No biological performance result.",
        "evaluation": {
            "evaluation_id": "fixed-sessions",
            "fingerprint": "evaluation-hash",
            "units": "cm/s",
            "coordinates": "x-right,y-up",
            "horizon_ms": 0,
            "purpose": "synthetic",
        },
        "baseline": {"run_id": "baseline-a", "digest": "a", "provenance": {}},
        "candidate": {"run_id": "candidate-b", "digest": "b", "provenance": {}},
        "tolerance": 0.1,
        "numerical_tolerance": 1e-9,
        "complete": True,
        "issues": [],
        "excluded_counts": {"evaluation": 0, "baseline": 0, "candidate": 0},
        "sessions": [
            {
                "session_id": "improved-session", "status": "valid", "n_expected": 1,
                "n_scored": 1, "baseline_rmse": 3, "candidate_rmse": 1, "delta": -2,
                "regression": False, "issues": [],
            },
            {
                "session_id": "worsened-session", "status": "valid", "n_expected": 1,
                "n_scored": 1, "baseline_rmse": 1, "candidate_rmse": 2, "delta": 1,
                "regression": True, "issues": [],
            },
        ],
        "pooled": {"baseline_rmse": 2.236, "candidate_rmse": 1.581,
                   "delta": -0.655, "n_samples": 2},
        "samples": [
            {"session_id": session, "sample_id": "sample-1", "timestamp": 0,
             "target_vx": 0, "target_vy": 0, "baseline_vx": baseline,
             "baseline_vy": 0, "candidate_vx": candidate, "candidate_vy": 0,
             "baseline_error": baseline, "candidate_error": candidate}
            for session, baseline, candidate in (
                ("improved-session", 3, 1), ("worsened-session", 1, 2)
            )
        ],
    }


class ReportTests(unittest.TestCase):
    def test_session_results_and_evidence_precede_full_metadata(self):
        result = _result()
        result["baseline"]["digest"] = "baseline-digest-below-results"
        result["candidate"]["digest"] = "candidate-digest-below-results"
        html = render_report(result)
        table_start = html.index('<section class="panel" id="comparison">')
        detail_start = html.index('<details class="session-detail"')
        metric_start = html.index('<h2>Metric and reproduction</h2>')
        identity_start = html.index('<h2>Comparison identity</h2>')
        self.assertLess(table_start, detail_start)
        self.assertLess(detail_start, metric_start)
        self.assertLess(metric_start, identity_start)
        self.assertIn(
            '</section><details class="session-detail"',
            html[table_start:detail_start + 50],
        )
        for run_or_set in ("baseline-a", "candidate-b", "fixed-sessions"):
            self.assertIn(run_or_set, html[:table_start])
        for digest in ("baseline-digest-below-results", "candidate-digest-below-results", "evaluation-hash"):
            self.assertNotIn(digest, html[:identity_start])
            self.assertIn(digest, html[identity_start:])

    def test_session_links_target_open_native_evidence_sections(self):
        parsed = _Tags()
        parsed.feed(render_report(_result()))
        links = {
            attrs["href"][1:]
            for tag, attrs in parsed.tags
            if tag == "a" and attrs.get("href", "").startswith("#session-")
        }
        targets = {
            attrs["id"]
            for tag, attrs in parsed.tags
            if tag == "details" and attrs.get("class") == "session-detail" and "open" in attrs
        }
        self.assertEqual(links, {"session-1", "session-2"})
        self.assertEqual(links, targets)

    def test_report_preserves_tradeoff_and_input(self):
        result = _result()
        original = copy.deepcopy(result)
        html = render_report(result)
        self.assertEqual(result, original)
        self.assertIn("Synthetic fixture. No biological performance result.", html)
        self.assertIn("Complete comparison", html)
        self.assertIn("Sample-weighted pooled RMSE", html)
        self.assertLess(html.index('>worsened-session</a>'), html.index('>improved-session</a>'))
        self.assertIn("Regression", html)
        self.assertIn("Paired error trace", html)
        self.assertIn('id="session-1" open', html)

    def test_untrusted_strings_cannot_create_markup_or_attributes(self):
        result = _result()
        attack = '\"><img src=x onerror="alert(1)"><script>alert(2)</script>&'
        result["description"] = attack
        for key in ("evaluation_id", "fingerprint", "units", "coordinates", "horizon_ms", "purpose"):
            result["evaluation"][key] = attack
        for key in ("baseline", "candidate"):
            result[key] = {"run_id": attack, "digest": attack, "provenance": {attack: attack}}
        result["issues"] = [attack]
        result["sessions"][0]["session_id"] = attack
        result["sessions"][0]["issues"] = [attack]
        result["samples"][0]["session_id"] = attack
        result["samples"][0]["sample_id"] = attack
        result["samples"][0]["timestamp"] = attack
        html = render_report(result)
        parsed = _Tags()
        parsed.feed(html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn(attack, html)
        self.assertFalse({tag for tag, _ in parsed.tags} & {"script", "img", "iframe", "link"})
        for _, attrs in parsed.tags:
            self.assertFalse(any(key.startswith("on") for key in attrs))
            for key in ("href", "src"):
                if key in attrs:
                    self.assertTrue(attrs[key].startswith("#"))
            if "id" in attrs:
                self.assertNotIn(attack, attrs["id"])

    def test_invalid_session_is_prominent_and_pooled_is_suppressed(self):
        result = _result()
        result["complete"] = False
        result["issues"] = ["Required session is invalid."]
        result["sessions"].append({
            "session_id": "invalid-session", "status": "invalid", "n_expected": 3,
            "n_scored": 0, "baseline_rmse": None, "candidate_rmse": None,
            "delta": None, "regression": None, "issues": ["Missing prediction: sample-3"],
        })
        html = render_report(result)
        self.assertIn("Incomplete comparison", html)
        self.assertIn("Missing prediction: sample-3", html)
        self.assertLess(html.index('>invalid-session</a>'), html.index('>worsened-session</a>'))
        self.assertIn("No complete pooled comparison is reported.", html)
        self.assertNotIn("Sample-weighted pooled RMSE, secondary context:", html)
        self.assertIn("This session was not scored as a valid pair.", html)

    def test_unset_tolerance_is_descriptive(self):
        result = _result()
        result["tolerance"] = None
        for session in result["sessions"]:
            session["regression"] = None
        html = render_report(result)
        self.assertIn("No regression reporting tolerance was specified", html)
        self.assertIn("Descriptive deltas only", html)
        self.assertNotIn("above tolerance</span>", html)

    def test_trace_and_sample_preview_are_bounded_and_labeled(self):
        result = _result()
        sample = result["samples"][1]
        result["samples"] = [
            {**sample, "sample_id": f"key-{i}", "timestamp": i,
             "baseline_error": i % 5, "candidate_error": 10 if i == 717 else 1}
            for i in range(1000)
        ]
        html = render_report(result)
        self.assertIn("Trace preview uses", html)
        self.assertIn("of 1,000 samples", html)
        self.assertIn("Showing 24 of 1,000 paired samples", html)
        self.assertIn("All samples and their identities remain in the saved scoring bundle", html)
        self.assertNotIn('>key-24</th>', html)
        parsed = _Tags()
        parsed.feed(html)
        for tag, attrs in parsed.tags:
            if tag == "polyline":
                self.assertLessEqual(len(attrs["points"].split()), 322)


if __name__ == "__main__":
    unittest.main()
