"""HTTP client with on-disk caching, retries with exponential backoff and per-host rate limiting (PRD FR-2)."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests

# Leading bytes used to reject bot-check / error pages that come back with HTTP 200.
MAGIC = {"xlsx": b"PK\x03\x04", "xml": b"<", "tsv": None}


class HttpError(RuntimeError):
    pass


class CachedHttp:
    def __init__(self, cache_dir: Path, http_cfg: dict, refresh: bool = False):
        self.cache_dir = Path(cache_dir) / "http"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = http_cfg["timeout_s"]
        self.retries = http_cfg["retries"]
        self.backoff = http_cfg["backoff_base_s"]
        self.min_interval = http_cfg["min_interval_s"]
        self.refresh = refresh
        self.session = requests.Session()
        self.session.headers["User-Agent"] = http_cfg["user_agent"]
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    # --- public -----------------------------------------------------------------
    def get(self, url: str, params: dict | None = None, expect: str | None = None) -> bytes:
        return self._fetch("GET", url, params=params, expect=expect)

    def post(self, url: str, data: dict, expect: str | None = None) -> bytes:
        return self._fetch("POST", url, data=data, expect=expect)

    def head_size(self, url: str) -> int | None:
        """Content-Length of a file, cached. None if the server does not report it."""
        key = self._key("HEAD", url)
        cached = self.cache_dir / f"{key}.json"
        if cached.exists() and not self.refresh:
            return json.loads(cached.read_text())["size"]
        resp = self._request("HEAD", url, allow_redirects=True)
        size = resp.headers.get("Content-Length")
        size = int(size) if size is not None else None
        cached.write_text(json.dumps({"url": url, "size": size}))
        return size

    # --- internals ----------------------------------------------------------------
    def _key(self, method: str, url: str, params=None, data=None) -> str:
        blob = json.dumps([method, url, sorted((params or {}).items()), sorted((data or {}).items())])
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    def _fetch(self, method, url, params=None, data=None, expect=None) -> bytes:
        key = self._key(method, url, params, data)
        body_path = self.cache_dir / f"{key}.bin"
        if body_path.exists() and not self.refresh:
            return body_path.read_bytes()
        resp = self._request(method, url, params=params, data=data)
        body = resp.content
        magic = MAGIC.get(expect or "")
        if magic and not body.lstrip().startswith(magic):
            raise HttpError(f"{method} {url}: unexpected payload (not {expect}); first bytes {body[:60]!r}")
        tmp = body_path.with_suffix(".tmp")
        tmp.write_bytes(body)
        tmp.replace(body_path)  # atomic, so an interrupted run never leaves a half-written cache entry
        full = url + ("?" + urlencode(params) if params else "")
        (self.cache_dir / f"{key}.meta.json").write_text(json.dumps({"method": method, "url": full, "data": data}))
        return body

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        with self._lock:
            wait = self._last.get(host, 0) + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.monotonic()

    def _request(self, method, url, **kw) -> requests.Response:
        err = None
        for attempt in range(self.retries):
            self._throttle(url)
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kw)
                if resp.status_code == 200:
                    return resp
                if resp.status_code not in (429, 500, 502, 503, 504):
                    raise HttpError(f"{method} {url}: HTTP {resp.status_code}")
                err = HttpError(f"{method} {url}: HTTP {resp.status_code}")
            except requests.RequestException as e:
                err = e
            time.sleep(self.backoff ** attempt)
        raise HttpError(f"{method} {url}: failed after {self.retries} attempts: {err}")
