"""Turn a stream of check results into a few alerts.

A check must fail `fail_after` runs in a row before it is reported DOWN (no alert for one
dropped packet), recovery is reported once, and an unchanged problem is repeated at most
every `repeat_hours`.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from .checks import Result


def evaluate(results: list[Result], state: dict, *, now: float | None = None,
             fail_after: int = 2, repeat_hours: float = 12) -> tuple[list[str], dict]:
    now = time.time() if now is None else now
    alerts: list[str] = []
    new_state = dict(state)
    for r in results:
        prev = state.get(r.name, {"fails": 0, "down": False, "alerted": 0.0})
        cur = dict(prev)
        if r.ok:
            if prev["down"]:
                alerts.append(f"✅ <b>{r.name}</b> back: {r.detail}")
            cur.update(fails=0, down=False, alerted=0.0)
        else:
            cur["fails"] = prev["fails"] + 1
            if cur["fails"] >= fail_after:
                due = now - prev.get("alerted", 0.0) >= repeat_hours * 3600
                if not prev["down"] or due:
                    alerts.append(f"🔴 <b>{r.name}</b>: {r.detail}")
                    cur["alerted"] = now
                cur["down"] = True
        new_state[r.name] = cur
    return alerts, new_state


def load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(path)


def append_history(path: Path, results: list[Result], now: float | None = None, keep_days: int = 35) -> None:
    now = time.time() if now is None else now
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text().splitlines() if path.exists() else []
    cutoff = now - keep_days * 86400
    kept = [ln for ln in lines if json.loads(ln)["t"] >= cutoff]
    kept += [json.dumps({"t": now, **asdict(r)}) for r in results]
    path.write_text("\n".join(kept) + "\n")


def summary(path: Path, days: int = 7, now: float | None = None) -> list[tuple[str, float, int | None]]:
    """[(check, uptime %, median ms)] over the last `days`."""
    now = time.time() if now is None else now
    rows = [json.loads(ln) for ln in path.read_text().splitlines()] if path.exists() else []
    rows = [r for r in rows if r["t"] >= now - days * 86400]
    out = []
    for name in sorted({r["name"] for r in rows}):
        mine = [r for r in rows if r["name"] == name]
        ms = sorted(r["ms"] for r in mine if r["ms"] is not None)
        out.append((name, 100 * sum(r["ok"] for r in mine) / len(mine), ms[len(ms) // 2] if ms else None))
    return out
