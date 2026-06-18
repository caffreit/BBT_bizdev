from __future__ import annotations

import html
import json
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import USER_AGENT, YC_ALGOLIA_API_KEY, YC_ALGOLIA_APP_ID


def fetch_raw_text(url: str) -> tuple[str, str | None]:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        raw = urlopen(req, timeout=25).read()
    except (OSError, URLError) as exc:
        return "", str(exc)
    return raw.decode("utf-8", "ignore"), None

def fetch_text(url: str) -> tuple[str, str | None]:
    text, error = fetch_raw_text(url)
    if error:
        return "", error
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text, None

def fetch_json(url: str, payload: dict) -> tuple[dict, str | None]:
    try:
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
                "X-Algolia-Application-Id": YC_ALGOLIA_APP_ID,
                "X-Algolia-API-Key": YC_ALGOLIA_API_KEY,
            },
        )
        raw = urlopen(req, timeout=30).read()
    except (OSError, URLError) as exc:
        return {}, str(exc)
    try:
        return json.loads(raw.decode("utf-8", "ignore")), None
    except json.JSONDecodeError as exc:
        return {}, f"JSON decode failed: {exc}"

def fetch_json_url(url: str) -> tuple[object, str | None]:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        raw = urlopen(req, timeout=30).read()
    except (OSError, URLError) as exc:
        return {}, str(exc)
    try:
        return json.loads(raw.decode("utf-8", "ignore")), None
    except json.JSONDecodeError as exc:
        return {}, f"JSON decode failed: {exc}"

