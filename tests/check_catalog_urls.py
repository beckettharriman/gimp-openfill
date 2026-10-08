# SPDX-License-Identifier: GPL-3.0-or-later
"""Network check (not a unit test): HEAD every URL in models/catalog.json.

    python tests/check_catalog_urls.py [--token HF_TOKEN]

Gated Hugging Face files answer 401/403 without a token; that counts as
"resolves" because the host exists and the gating is expected.
"""
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gimp-stable-boy"))
from stable_boy.catalog import load_catalog  # noqa: E402


def head(url, token=None):
    headers = {"User-Agent": "gimp-stable-boy url check"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, headers=headers, method="HEAD"), timeout=30) as r:
            return r.status, r.headers.get("Content-Length") or r.headers.get("X-Linked-Size")
    except HTTPError as e:
        return e.code, e.headers.get("X-Linked-Size")
    except URLError as e:
        return None, str(e)


def main():
    token = sys.argv[sys.argv.index("--token") + 1] if "--token" in sys.argv else None
    entries = load_catalog(Path(__file__).resolve().parent.parent / "models" / "catalog.json")
    bad = 0
    for e in entries:
        for label, url in (("page", e.page), ("license", e.license_url)):
            status, _ = head(url, token)
            ok = status in (200, 301, 302, 303, 307, 308)
            bad += not ok
            print(f"{'ok ' if ok else 'BAD'} {e.id:28s} {label:8s} {status} {url}")
        for f in e.files:
            status, size = head(f.url, token)
            ok = status in (200, 302) or (f.gated and status in (401, 403))
            size_ok = size is None or f.size is None or int(size) == f.size or status in (401, 403)
            bad += not (ok and size_ok)
            print(f"{'ok ' if ok and size_ok else 'BAD'} {e.id:28s} {f.role:8s} {status} size={size} expected={f.size} {f.url}")
    print("problems:", bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
