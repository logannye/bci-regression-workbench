"""Validate both reviewed static demos; never run a model or scorer."""
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
FILES = {'index.html', 'session_metrics.csv', 'publication.json'}
EXPECTED_FILES = FILES | {f'indy/{name}' for name in FILES}
NOTICE_START = '<!-- PUBLIC-DEMO-NOTICE-START -->'
NOTICE_END = '<!-- PUBLIC-DEMO-NOTICE-END -->'
PUBLICATIONS = [
    ('', '4f46058f77847b29f3db1834fd02777de520f8739636e4cc7b8f2af7e90aafcb',
     'docs/human-demo/result-v1.json', '10.5061/dryad.n2z34tn5s',
     'https://creativecommons.org/publicdomain/zero/1.0/', 12),
    ('indy', '791b5eb1af655f3e816f49a91851f88ca0db0f8c884ba7f2f6506f8359da7bba',
     'docs/public-demo/result-v1.json', '10.5281/zenodo.3854034',
     'https://creativecommons.org/licenses/by/4.0/', 3),
]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.scripts = set(), [], 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            require(attrs['id'] not in self.ids, 'Duplicate HTML id')
            self.ids.add(attrs['id'])
        require(tag not in {'iframe', 'object', 'embed', 'form', 'base'}, 'Unexpected embedded content')
        require(not any(k in attrs for k in ('src', 'srcset', 'action')), 'External or embedded asset')
        require(not any(k.startswith('on') for k in attrs), 'Inline event handler')
        if tag == 'script':
            self.scripts += 1
        if 'href' in attrs:
            require(tag == 'a', 'Unexpected non-navigation reference')
            self.links.append(attrs['href'])


def main():
    entries = list(SITE.rglob('*'))
    require(not any(p.is_symlink() for p in entries), 'Publication symlink')
    require({p.relative_to(SITE).as_posix() for p in entries if p.is_dir()} == {'indy'}, 'Unexpected site directory')
    require({p.relative_to(SITE).as_posix() for p in entries if p.is_file()} == EXPECTED_FILES, 'Unreviewed published file')
    require(sum(p.stat().st_size for p in entries if p.is_file()) < 750_000, 'Unexpected publication size')
    for directory, expected_report, receipt_path, doi, license_url, n_sessions in PUBLICATIONS:
        root = SITE / directory
        publication = json.loads((root / 'publication.json').read_text())
        require(set(publication['files']) == FILES - {'publication.json'}, 'Incomplete publication manifest')
        for name, digest in publication['files'].items():
            require(sha256((root / name).read_bytes()).hexdigest() == digest, f'Published bytes changed: {directory}/{name}')
        raw = (root / 'index.html').read_text()
        require(raw.count(NOTICE_START) == raw.count(NOTICE_END) == 1, 'Missing or repeated public notice')
        original = re.sub(re.escape(NOTICE_START) + '.*?' + re.escape(NOTICE_END), '', raw, flags=re.S)
        require(sha256(original.encode()).hexdigest() == expected_report, 'Reviewed report changed')
        require(publication['original_report_sha256'] == expected_report, 'Report identity mismatch')
        receipt = json.loads((ROOT / receipt_path).read_text())
        require(sha256((root / 'session_metrics.csv').read_bytes()).hexdigest() == receipt['artifact_hashes']['comparison/session_metrics.csv'], 'Frozen scores changed')
        require(not re.search(r'(?:file://|/Users/|/home/|/private/|gh[pousr]_[A-Za-z0-9]{20,})', raw), 'Private path or credential-like content')
        require(not re.search(r'(?:fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|@import|url\s*\()', raw), 'Unexpected network behavior')
        page = Page(); page.feed(raw)
        require(page.scripts == 1, 'Expected one fixed report script')
        for href in page.links:
            if href.startswith('#'):
                require(href[1:] in page.ids, f'Broken fragment: {href}')
            elif href in FILES | {'indy/index.html'}:
                require((root / href).is_file(), f'Missing published link: {href}')
            else:
                url = urlsplit(href)
                require(url.scheme == 'https' and url.hostname in {'github.com', 'doi.org', 'creativecommons.org'}, f'Unexpected link: {href}')
        require(f'https://doi.org/{doi}' in page.links and license_url in page.links, 'Missing dataset attribution/license')
        require(all(f'session-{i}' in page.ids for i in range(1, n_sessions + 1)), 'Missing session panel')
        if not directory:
            require('Inferred cursor-to-target vectors.' in raw and 'not measured intended velocity' in raw, 'Missing inferred-target disclosure')
            require(publication['target_kind'] == 'inferred_cursor_to_target_vector', 'Wrong target kind')
    print('Public demos verified: six reviewed files; twelve human days and the unchanged three-day Indy report.')


if __name__ == '__main__':
    main()
