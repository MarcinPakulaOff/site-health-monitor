"""site-monitor run|summary --config sites.json --state-dir DIR"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import notify, state
from .checks import DEFAULT_UA, Result, check_http, check_sitemap, check_ssl


def run_checks(cfg: dict) -> list[Result]:
    ua = cfg.get("user_agent", DEFAULT_UA)
    results = [check_http(c["name"], c["url"], expect=c.get("expect"), contains=c.get("contains"),
                          max_ms=c.get("max_ms"), ua=ua) for c in cfg.get("http", [])]
    results += [check_ssl(h, cfg.get("ssl_warn_days", 14)) for h in cfg.get("ssl", [])]
    if sm := cfg.get("sitemap"):
        results.append(check_sitemap(sm["url"], sm["min_urls"], ua))
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="site-monitor")
    ap.add_argument("cmd", choices=["run", "summary"])
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--state-dir", type=Path, default=Path(".site-monitor"))
    ap.add_argument("--quiet", action="store_true", help="run: print nothing when there is no alert")
    args = ap.parse_args(argv)
    cfg = json.loads(args.config.read_text())
    st_path, hist_path = args.state_dir / "state.json", args.state_dir / "history.jsonl"

    if args.cmd == "summary":
        rows = state.summary(hist_path, days=7)
        if not rows:
            notify.send("📈 <b>Site monitor</b>: no data yet")
            return 0
        lines = [f"{'✅' if up >= 99.5 else '⚠️'} {name}: {up:.1f}%" + (f", {ms} ms" if ms else "")
                 for name, up, ms in rows]
        notify.send(f"📈 <b>{cfg.get('title', 'Site monitor')} — 7 days</b>\n" + "\n".join(lines))
        return 0

    results = run_checks(cfg)
    state.append_history(hist_path, results)
    alerts, new = state.evaluate(results, state.load(st_path), fail_after=cfg.get("fail_after", 2))
    state.save(st_path, new)
    if alerts:
        notify.send(f"🛰 <b>{cfg.get('title', 'Site monitor')}</b>\n" + "\n".join(alerts))
    elif not args.quiet:
        for r in results:
            print(f"{'ok ' if r.ok else 'BAD'} {r.name}: {r.detail}" + (f" ({r.ms} ms)" if r.ms else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
