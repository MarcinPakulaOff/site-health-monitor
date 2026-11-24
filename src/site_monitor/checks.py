"""The checks themselves. Each returns a plain result; deciding what to alert on is in state.py."""

from __future__ import annotations

import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

DEFAULT_UA = "Mozilla/5.0 (compatible; site-health-monitor/0.1)"


@dataclass(frozen=True)
class Result:
    name: str
    ok: bool
    detail: str
    ms: int | None = None


def _fetch(url: str, ua: str, timeout: float) -> tuple[int, bytes, int]:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(2_000_000)
            status = resp.status
    except urllib.error.HTTPError as exc:
        body, status = exc.read(200_000), exc.code
    return status, body, int((time.monotonic() - start) * 1000)


def check_http(name: str, url: str, *, expect: list[int] | None = None, contains: str | None = None,
               max_ms: int | None = None, ua: str = DEFAULT_UA, timeout: float = 15) -> Result:
    expect = expect or [200]
    try:
        status, body, ms = _fetch(url, ua, timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return Result(name, False, f"no answer ({getattr(exc, 'reason', exc)})")
    if status not in expect:
        return Result(name, False, f"HTTP {status}", ms)
    if contains and contains.encode() not in body:
        return Result(name, False, f"HTTP {status}, but '{contains}' is missing", ms)
    if max_ms and ms > max_ms:
        return Result(name, False, f"slow: {ms} ms (limit {max_ms})", ms)
    return Result(name, True, f"HTTP {status}", ms)


def ssl_days_left(host: str, port: int = 443, timeout: float = 10) -> int:
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
    expires = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    return (expires - datetime.now(timezone.utc)).days


def check_ssl(host: str, warn_days: int = 14) -> Result:
    name = f"ssl:{host}"
    try:
        days = ssl_days_left(host)
    except (OSError, ssl.SSLError) as exc:
        return Result(name, False, f"TLS error ({exc})")
    if days < warn_days:
        return Result(name, False, f"certificate expires in {days} days")
    return Result(name, True, f"{days} days left")


LOC = re.compile(rb"<loc>")


def check_sitemap(url: str, min_urls: int, ua: str = DEFAULT_UA) -> Result:
    """A sitemap that suddenly shrinks usually means a broken build, not fewer pages."""
    name = "sitemap"
    try:
        status, body, ms = _fetch(url, ua, 20)
    except (urllib.error.URLError, OSError) as exc:
        return Result(name, False, f"no answer ({exc})")
    if status != 200:
        return Result(name, False, f"HTTP {status}", ms)
    count = len(LOC.findall(body))
    if count < min_urls:
        return Result(name, False, f"{count} URLs (expected at least {min_urls})", ms)
    return Result(name, True, f"{count} URLs", ms)
