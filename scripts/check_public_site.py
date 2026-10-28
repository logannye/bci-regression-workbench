"""Check the small, reviewed static publication; never run a model or scorer."""

from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
EXPECTED_FILES = {"index.html", "session_metrics.csv", "publication.json"}
ORIGINAL_REPORT_SHA256 = "791b5eb1af655f3e816f49a91851f88ca0db0f8c884ba7f2f6506f8359da7bba"
NOTICE_START = "<!-- PUBLIC-DEMO-NOTICE-START -->"
NOTICE_END = "<!-- PUBLIC-DEMO-NOTICE-END -->"


def require(condition, message):
    if not condition:
        raise SystemExit(message)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            require(attrs["id"] not in self.ids, "Duplicate HTML id")
            self.ids.add(attrs["id"])
        require(tag not in {"iframe", "object", "embed", "form", "base"}, "Unexpected embedded content")
        require(not any(key in attrs for key in ("src", "srcset", "action")), "External or embedded asset")
        require(not any(key.startswith("on") for key in attrs), "Inline event handler")
        if tag == "script":
            self.scripts += 1
        if "href" in attrs:
            require(tag == "a", "Unexpected non-navigation reference")
            self.links.append(attrs["href"])


def main():
    entries = list(SITE.rglob("*"))
    require(all(p.is_file() and not p.is_symlink() for p in entries), "Unexpected site directory or symlink")
    require({p.name for p in entries} == EXPECTED_FILES, "Unreviewed file in publication directory")
    require(sum(p.stat().st_size for p in entries) < 150_000, "Unexpected publication size")
    publication = json.loads((SITE / "publication.json").read_text())
    require(set(publication["files"]) == EXPECTED_FILES - {"publication.json"}, "Incomplete publication manifest")
    for name, digest in publication["files"].items():
        require(sha256((SITE / name).read_bytes()).hexdigest() == digest, f"Published bytes changed: {name}")

    raw = (SITE / "index.html").read_text()
    require(raw.count(NOTICE_START) == raw.count(NOTICE_END) == 1, "Missing or repeated public notice")
    original = re.sub(re.escape(NOTICE_START) + ".*?" + re.escape(NOTICE_END), "", raw, flags=re.S)
    require(sha256(original.encode()).hexdigest() == ORIGINAL_REPORT_SHA256, "Original report content changed")
    require(publication["original_report_sha256"] == ORIGINAL_REPORT_SHA256, "Wrong original report identity")
    receipt = json.loads((ROOT / "docs/public-demo/result-v1.json").read_text())
    csv_digest = sha256((SITE / "session_metrics.csv").read_bytes()).hexdigest()
    require(csv_digest == receipt["artifact_hashes"]["comparison/session_metrics.csv"], "Frozen public scores changed")

    # These checks supplement the exact reviewed-report hash, not a general sanitizer.
    require(not re.search(r"(?:file://|/Users/|/home/|/private/|gh[pousr]_[A-Za-z0-9]{20,})", raw), "Private path or credential-like content")
    require(not re.search(r"(?:fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|@import|url\s*\()", raw), "Unexpected network behavior")
    page = Page()
    page.feed(raw)
    require(page.scripts == 1, "Expected the report's one fixed script")
    hosts = {"github.com", "doi.org", "creativecommons.org"}
    for href in page.links:
        if href.startswith("#"):
            require(href[1:] in page.ids, f"Broken fragment: {href}")
        elif href in EXPECTED_FILES:
            require((SITE / href).is_file(), f"Missing published link: {href}")
        else:
            url = urlsplit(href)
            require(url.scheme == "https" and url.hostname in hosts, f"Unexpected link: {href}")
    require("https://doi.org/10.5281/zenodo.3854034" in page.links, "Missing dataset attribution")
    require("https://creativecommons.org/licenses/by/4.0/" in page.links, "Missing dataset license")
    require(all(f"session-{i}" in page.ids for i in range(1, 4)), "Missing public session")
    print("Public demo verified: 3 reviewed files; unchanged report, script, and frozen session scores.")


if __name__ == "__main__":
    main()
