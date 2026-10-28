"""Behavior, evidence boundaries, and unsafe-text checks for the portable report."""

import copy
from html.parser import HTMLParser
import unittest

from bci_regression.report import _trace_indices, render_report


class _Node:
    def __init__(self, tag, attrs=(), parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []

    @property
    def text(self):
        return "".join(child.text if isinstance(child, _Node) else child for child in self.children)

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()


class _Document(HTMLParser):
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = _Node("document")
        self.stack = [self.root]
        self.nodes = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        self.nodes.append(node)
        if tag not in self._VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def find(self, *, tag=None, id=None, cls=None):
        return [node for node in self.nodes
                if (tag is None or node.tag == tag)
                and (id is None or node.attrs.get("id") == id)
                and (cls is None or node.has_class(cls))]

    def one(self, **criteria):
        matches = self.find(**criteria)
        if len(matches) != 1:
            raise AssertionError(f"Expected one {criteria}, found {len(matches)}")
        return matches[0]


def _result():
    return {
        "schema_version": "1",
        "description": "Synthetic fixture. No biological performance result.",
        "evaluation": {
            "evaluation_id": "fixed-sessions", "fingerprint": "evaluation-hash",
            "units": "cm/s", "coordinates": "x-right,y-up", "horizon_ms": 0,
            "purpose": "synthetic",
        },
        "baseline": {"run_id": "baseline-a", "digest": "a", "provenance": {}},
        "candidate": {"run_id": "candidate-b", "digest": "b", "provenance": {}},
        "tolerance": 0.1, "numerical_tolerance": 1e-9, "complete": True,
        "issues": [],
        "excluded_counts": {"evaluation": 0, "baseline": 0, "candidate": 0},
        "sessions": [
            {"session_id": "improved-session", "status": "valid", "n_expected": 1,
             "n_scored": 1, "baseline_rmse": 3, "candidate_rmse": 1, "delta": -2,
             "regression": False, "issues": []},
            {"session_id": "worsened-session", "status": "valid", "n_expected": 1,
             "n_scored": 1, "baseline_rmse": 1, "candidate_rmse": 2, "delta": 1,
             "regression": True, "issues": []},
        ],
        "pooled": {"baseline_rmse": 2.236, "candidate_rmse": 1.581,
                   "delta": -0.655, "n_samples": 2},
        "samples": [
            {"session_id": session, "sample_id": "sample-1", "timestamp": 0,
             "target_vx": 0, "target_vy": 0, "baseline_vx": baseline,
             "baseline_vy": 0, "candidate_vx": candidate, "candidate_vy": 0,
             "baseline_error": baseline, "candidate_error": candidate}
            for session, baseline, candidate in (
                ("improved-session", 3, 1), ("worsened-session", 1, 2))
        ],
    }


def _session_rows(document):
    return [node for node in document.find(tag="tr") if "data-session-row" in node.attrs]


class ReportTests(unittest.TestCase):
    def test_session_results_and_evidence_precede_collapsed_full_metadata(self):
        result = _result()
        result["baseline"]["digest"] = "baseline-digest-below-results"
        result["candidate"]["digest"] = "candidate-digest-below-results"
        document = _Document(render_report(result))
        table = document.one(tag="table", id="comparison")
        panels = document.find(tag="section", cls="session-detail")
        evidence = document.one(tag="details", id="comparison-evidence")
        self.assertNotIn("open", evidence.attrs)
        self.assertLess(document.nodes.index(table), document.nodes.index(panels[0]))
        self.assertLess(document.nodes.index(panels[-1]), document.nodes.index(evidence))
        header = document.one(tag="header")
        for run_or_set in ("baseline-a", "candidate-b", "fixed-sessions"):
            self.assertIn(run_or_set, header.text)
        for digest in ("baseline-digest-below-results", "candidate-digest-below-results", "evaluation-hash"):
            self.assertNotIn(digest, header.text)
            self.assertIn(digest, evidence.text)
        self.assertIn("Vector RMSE", evidence.text)
        self.assertIn("Producer-supplied provenance", evidence.text)
        self.assertIn("not independently verified", evidence.text)

    def test_native_session_links_target_visible_accessible_evidence_without_javascript(self):
        document = _Document(render_report(_result()))
        root = document.one(tag="main", id="bci-report")
        self.assertFalse(root.has_class("enhanced"))
        links = document.find(tag="a", cls="session-link")
        panels = document.find(tag="section", cls="session-detail")
        self.assertEqual({node.attrs["href"] for node in links}, {"#session-1", "#session-2"})
        self.assertEqual({node.attrs["id"] for node in panels}, {"session-1", "session-2"})
        for panel in panels:
            self.assertNotIn("hidden", panel.attrs)
            heading = document.one(id=panel.attrs["aria-labelledby"])
            self.assertEqual(heading.tag, "h2")
            self.assertEqual(heading.attrs.get("tabindex"), "-1")
        for link in links:
            self.assertIn("data-session-link", link.attrs)
            self.assertEqual(link.attrs["aria-controls"], link.attrs["href"][1:])
            self.assertNotIn("onclick", link.attrs)
        announcement = document.one(id="selection-announcement")
        self.assertEqual(announcement.attrs.get("role"), "status")
        self.assertEqual(announcement.attrs.get("aria-live"), "polite")
        ids = [node.attrs["id"] for node in document.nodes if "id" in node.attrs]
        self.assertEqual(len(ids), len(set(ids)))

    def test_report_preserves_tradeoff_input_and_session_order(self):
        result = _result()
        original = copy.deepcopy(result)
        document = _Document(render_report(result))
        self.assertEqual(result, original)
        self.assertIn("Synthetic fixture. No biological performance result.", document.root.text)
        self.assertIn("Complete comparison", document.root.text)
        self.assertIn("Sample-weighted pooled RMSE", document.root.text)
        links = document.find(tag="a", cls="session-link")
        self.assertEqual([node.text.strip() for node in links], ["worsened-session", "improved-session"])
        rows = _session_rows(document)
        self.assertIn("Regression", rows[0].text)
        self.assertNotIn("Regression", rows[1].text)
        self.assertIn("Paired error trace", document.one(id="session-1").text)
        self.assertIn("Evaluation sample order", document.one(id="session-1").text)

    def test_untrusted_strings_cannot_create_markup_attributes_or_script_contents(self):
        normal = _Document(render_report(_result()))
        result = _result()
        attack = '\"><img src=x onerror="alert(1)"></script><script data-injected>fetch("evil")</script><style>body{display:none}</style>&'
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
        document = _Document(html)
        self.assertIn("&lt;script", html)
        self.assertNotIn(attack, html)
        self.assertFalse({node.tag for node in document.nodes} & {"img", "iframe", "link", "object", "embed"})
        self.assertEqual(len(document.find(tag="style")), 1)
        self.assertEqual(document.one(tag="style").text, normal.one(tag="style").text)
        script = document.one(tag="script", id="report-interaction")
        self.assertEqual(len(document.find(tag="script")), 1)
        self.assertEqual(script.text, normal.one(tag="script", id="report-interaction").text)
        self.assertNotIn("data-injected", script.text)
        self.assertNotRegex(script.text, r"\b(?:eval|Function|fetch)\s*\(")
        self.assertNotIn("innerHTML", script.text)
        for node in document.nodes:
            self.assertFalse(any(key.startswith("on") for key in node.attrs))
            for key in ("href", "src"):
                if key in node.attrs:
                    self.assertTrue(node.attrs[key].startswith("#"))
            for key, value in node.attrs.items():
                # HTMLParser decodes escaped attribute values. Text-only titles
                # and accessible labels can safely retain the complete producer text.
                if value is not None and key not in {"title", "aria-label"}:
                    self.assertNotIn(attack, value)

    def test_invalid_session_is_prominent_null_and_not_treated_as_a_regression(self):
        result = _result()
        result["complete"] = False
        result["pooled"] = None
        result["issues"] = ["Required session is invalid."]
        result["sessions"].append({
            "session_id": "invalid-session", "status": "invalid", "n_expected": 3,
            "n_scored": 0, "baseline_rmse": None, "candidate_rmse": None,
            "delta": None, "regression": None, "issues": ["Missing prediction: sample-3"],
        })
        document = _Document(render_report(result))
        self.assertIn("Incomplete comparison", document.root.text)
        rows = _session_rows(document)
        self.assertIn("invalid-session", rows[0].text)
        self.assertIn("Invalid", rows[0].text)
        self.assertNotIn("Regression", rows[0].text)
        self.assertNotIn("Within tolerance", rows[0].text)
        self.assertRegex(rows[0].text, r"0\s*/\s*3")
        self.assertGreaterEqual(rows[0].text.count("—"), 3)
        panel = document.one(id="session-1")
        self.assertIn("Missing prediction: sample-3", panel.text)
        self.assertIn("This session was not scored as a valid pair.", panel.text)
        self.assertFalse(any(node.tag == "svg" and self._inside(node, panel) for node in document.nodes))
        self.assertIn("No complete pooled comparison is reported.", document.root.text)
        self.assertNotIn("Sample-weighted pooled RMSE, secondary context:", document.root.text)

    @staticmethod
    def _inside(node, parent):
        while node.parent is not None:
            node = node.parent
            if node is parent:
                return True
        return False

    def test_global_issue_alone_keeps_comparison_incomplete_without_hiding_valid_sessions(self):
        result = _result()
        result["complete"] = False
        result["issues"] = ["Candidate contains unknown session: extra-recording"]
        # Suppress pooled context even if an inconsistent caller retained a value.
        document = _Document(render_report(result))
        self.assertIn("Incomplete comparison", document.root.text)
        status = document.one(tag="section", cls="status")
        self.assertIn("Candidate contains unknown session: extra-recording", status.text)
        self.assertIn("No complete pooled comparison is reported.", document.root.text)
        self.assertNotIn("Sample-weighted pooled RMSE, secondary context:", document.root.text)
        self.assertEqual(len(_session_rows(document)), 2)
        self.assertEqual(len(document.find(tag="section", cls="session-detail")), 2)
        self.assertTrue(all("Invalid" not in row.text for row in _session_rows(document)))

    def test_unset_tolerance_is_descriptive_even_when_candidate_error_is_higher(self):
        result = _result()
        result["tolerance"] = None
        for session in result["sessions"]:
            session["regression"] = None
        document = _Document(render_report(result))
        self.assertIn("No regression reporting tolerance was specified", document.root.text)
        self.assertIn("Descriptive deltas only", document.root.text)
        self.assertIn("no categorical regression claim is made", document.root.text)
        for row in _session_rows(document):
            self.assertIn("Descriptive", row.text)
            self.assertNotIn("Regression", row.text)
            self.assertNotIn("Within tolerance", row.text)
        self.assertIn("+1", _session_rows(document)[0].text)

    def test_rounding_does_not_change_supplied_flags_or_full_precision_values(self):
        result = _result()
        result["tolerance"] = 1
        result["sessions"][0].update(baseline_rmse=1.23456789, candidate_rmse=2.23456789,
                                      delta=1.0, regression=False)
        result["sessions"][1].update(baseline_rmse=1.23456789, candidate_rmse=2.23456829,
                                      delta=1.0000004, regression=True)
        original = copy.deepcopy(result)
        document = _Document(render_report(result))
        rows = _session_rows(document)
        self.assertIn("worsened-session", rows[0].text)
        self.assertIn("Regression", rows[0].text)
        self.assertIn("Within tolerance", rows[1].text)
        self.assertIn("1.23", rows[0].text)
        self.assertNotIn("1.23456789", rows[0].text)
        exact_values = [node.attrs["title"] for node in document.nodes
                        if "title" in node.attrs and self._inside(node, rows[0])]
        self.assertIn("1.23456789", exact_values)
        self.assertIn("1.0000004", exact_values)
        self.assertEqual(result, original)

    def test_small_nonzero_change_is_not_displayed_as_zero(self):
        result = _result()
        result["tolerance"] = 0
        result["sessions"][1].update(candidate_rmse=1.00000001, delta=1e-8, regression=True)
        document = _Document(render_report(result))
        first = _session_rows(document)[0]
        change = next(node for node in document.find(tag="td", cls="delta")
                      if self._inside(node, first))
        self.assertGreater(float(change.text), 0)
        self.assertIn("Regression", first.text)

    def test_supporting_samples_and_provenance_are_secondary_and_collapsed(self):
        document = _Document(render_report(_result()))
        supporting = document.find(tag="details", cls="supporting-samples")
        self.assertEqual(len(supporting), 2)
        for node in supporting:
            self.assertNotIn("open", node.attrs)
            self.assertIn("Showing 1 of 1 paired sample", node.text)
            self.assertIn("All samples and their identities remain in the saved scoring bundle", node.text)
        evidence = document.one(tag="details", id="comparison-evidence")
        self.assertNotIn("open", evidence.attrs)
        self.assertIn("numerical", evidence.text.lower())
        self.assertIn("recompute", evidence.text.lower())

    def test_trace_and_sample_preview_are_bounded_and_labeled(self):
        result = _result()
        sample = result["samples"][1]
        result["samples"] = [
            {**sample, "sample_id": f"key-{i}", "timestamp": i,
             "baseline_error": i % 5, "candidate_error": 10 if i == 717 else 1}
            for i in range(1000)
        ]
        result["sessions"][1].update(n_expected=1000, n_scored=1000)
        original = copy.deepcopy(result)
        document = _Document(render_report(result))
        self.assertIn("Trace preview uses", document.root.text)
        self.assertIn("of 1,000 samples", document.root.text)
        self.assertIn("minima and maxima", document.root.text)
        self.assertIn("Showing 24 of 1,000 paired samples", document.root.text)
        self.assertIn("All samples and their identities remain in the saved scoring bundle", document.root.text)
        self.assertRegex(_session_rows(document)[0].text, r"1,?000\s*/\s*1,?000")
        sample_tables = document.find(tag="table", cls="sample-table")
        self.assertEqual(len(sample_tables), 1)
        table = sample_tables[0]
        preview_keys = [node.text for node in document.find(tag="th")
                        if node.attrs.get("scope") == "row" and self._inside(node, table)]
        self.assertEqual(preview_keys, [f"key-{i}" for i in range(24)])
        for node in document.find(tag="polyline"):
            self.assertLessEqual(len(node.attrs["points"].split()), 322)
        self.assertEqual(result, original)

    def test_trace_selection_preserves_both_series_bucket_extrema_and_endpoints(self):
        samples = [dict(baseline_error=(index * 19) % 137,
                        candidate_error=(index * 37) % 181) for index in range(1003)]
        samples[717]["candidate_error"] = 10000
        selected = _trace_indices(samples)
        self.assertEqual(selected, sorted(set(selected)))
        self.assertLessEqual(len(selected), 322)
        self.assertIn(0, selected)
        self.assertIn(len(samples) - 1, selected)
        self.assertIn(717, selected)
        for bucket in range(80):
            indices = range(bucket * len(samples) // 80, (bucket + 1) * len(samples) // 80)
            for field in ("baseline_error", "candidate_error"):
                self.assertIn(min(indices, key=lambda i: samples[i][field]), selected)
                self.assertIn(max(indices, key=lambda i: samples[i][field]), selected)
        self.assertEqual(_trace_indices(samples[:17]), list(range(17)))

    def test_valid_session_traces_share_scale_and_invalid_samples_do_not_expand_it(self):
        result = _result()
        result["complete"] = False
        result["pooled"] = None
        result["sessions"].append({
            "session_id": "invalid-session", "status": "invalid", "n_expected": 1,
            "n_scored": 0, "baseline_rmse": None, "candidate_rmse": None,
            "delta": None, "regression": None, "issues": ["Unscored evidence"],
        })
        result["samples"].append({**result["samples"][0], "session_id": "invalid-session",
                                   "baseline_error": 1e9, "candidate_error": 1e9})
        document = _Document(render_report(result))
        captions = document.find(tag="figcaption")
        self.assertEqual(len(captions), 2)
        self.assertTrue(all("Shared y-axis across valid sessions: 0–3.00 cm/s" in node.text
                            for node in captions))
        for panel in document.find(tag="section", cls="session-detail"):
            if "invalid-session" in panel.text:
                continue
            svg = next(node for node in document.find(tag="svg") if self._inside(node, panel))
            height = float(svg.attrs["viewbox"].split()[3])
            name = document.one(id=panel.attrs["aria-labelledby"]).text
            sample = next(row for row in result["samples"] if row["session_id"] == name)
            for kind in ("baseline", "candidate"):
                point = next(node for node in document.find(tag="circle", cls=kind)
                             if self._inside(node, panel))
                self.assertAlmostEqual(float(point.attrs["cy"]),
                                       height * (1 - sample[f"{kind}_error"] / 3), places=3)

    def test_long_session_names_remain_complete_text_with_generated_stable_anchors(self):
        result = _result()
        name = 'recording / "quoted" <literal> & ' + "very-long-name-" * 60
        result["sessions"][1]["session_id"] = name
        result["samples"][1]["session_id"] = name
        document = _Document(render_report(result))
        links = document.find(tag="a", cls="session-link")
        self.assertEqual(links[0].text.strip(), name)
        self.assertEqual(links[0].attrs["href"], "#session-1")
        heading = document.one(id="session-1-heading")
        self.assertIn(name, heading.text)
        self.assertFalse(document.find(tag="literal"))
        for node in document.nodes:
            if "id" in node.attrs:
                self.assertNotIn(name, node.attrs["id"])


if __name__ == "__main__":
    unittest.main()
