#!/usr/bin/env python3
"""Frozen acceptance grader for the racing-game pilot.

Runs the identical checklist against either arm. Usage:

    python grader.py <path-to-arm-dir> [--json out.json]

Uses Playwright's Chromium with the system Edge channel so no browser
download is required. Loads the game over file:// which also exercises AC9.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

from playwright.sync_api import sync_playwright

CANVAS_W, CANVAS_H = 960, 600
CX, CY, HX, HY, R, THW = 480, 300, 348, 188, 92, 42


def sdf_js(px, py):
    """Mirror of the frozen centreline SDF, evaluated inside the page."""
    return """
    (([px, py]) => {
      const CX=480, CY=300, HX=348, HY=188, R=92;
      const qx = Math.abs(px-CX) - (HX-R);
      const qy = Math.abs(py-CY) - (HY-R);
      const ax = Math.max(qx,0), ay = Math.max(qy,0);
      return Math.hypot(ax,ay) + Math.min(Math.max(qx,qy),0) - R;
    })""" + f"([{px}, {py}])"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm_dir")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    arm = pathlib.Path(args.arm_dir).resolve()
    index = arm / "index.html"
    checks = {}

    def record(cid, ok, method, detail):
        checks[cid] = {"pass": bool(ok), "method": method, "detail": detail}

    if not index.is_file():
        record("AC1", False, "mechanical", "index.html missing at arm root")
        _emit(checks, args.json)
        return 1

    root_html = [p for p in arm.glob("*.html") if p.is_file()]
    record("AC10", len(root_html) == 1, "mechanical",
           "root html files: %s" % [p.name for p in root_html])

    src = index.read_text(encoding="utf-8", errors="replace")

    console_errors, page_errors, requests, bad_requests = [], [], [], []
    samples = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": CANVAS_W + 80, "height": CANVAS_H + 80})
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        def on_request(req):
            requests.append(req.url)
            if not (req.url.startswith("file://") or req.url.startswith("data:")
                    or req.url.startswith("blob:")):
                bad_requests.append(req.url)

        page.on("request", on_request)
        page.goto(index.as_uri())
        page.wait_for_timeout(700)

        has_debug = page.evaluate("() => !!window.__racingDebug")
        d0 = page.evaluate("() => window.__racingDebug") if has_debug else None
        page.wait_for_timeout(500)
        d1 = page.evaluate("() => window.__racingDebug") if has_debug else None

        # AC1 -----------------------------------------------------------------
        record("AC1", not console_errors and not page_errors, "mechanical",
               "console_errors=%s page_errors=%s" % (console_errors[:4], page_errors[:4]))

        # AC2 -----------------------------------------------------------------
        canvas = page.evaluate("""() => {
            const c = document.querySelector('canvas');
            if (!c) return null;
            const r = c.getBoundingClientRect();
            return {w: c.width, h: c.height, cw: r.width, ch: r.height};
        }""")
        advanced = bool(d0 and d1 and d1["frame"] > d0["frame"])
        ok2 = bool(canvas and canvas["w"] > 0 and canvas["h"] > 0 and advanced)
        record("AC2", ok2, "mechanical",
               "canvas=%s frame_advanced=%s (%s->%s)"
               % (canvas, advanced, d0 and d0["frame"], d1 and d1["frame"]))

        # AC5 / AC7 (HUD) -----------------------------------------------------
        # Graded through the frozen __racingDebug contract (Amendment 1), not
        # through arm-specific DOM ids which the spec never pinned.
        body_text = page.evaluate("() => document.body.innerText || ''")
        record("AC5", bool(d1 and d1["lap"] == 1 and d1["totalLaps"] == 3), "mechanical",
               "lap=%s totalLaps=%s" % (d1 and d1["lap"], d1 and d1["totalLaps"]))
        has_fields = bool(d1) and all(
            k in d1 and d1[k] is not None
            for k in ("speed", "lap", "totalLaps", "lapTime")
        ) and ("bestLap" in d1)
        shows_numbers = bool(re.search(r"\d+\.\d+", body_text)) and "3" in body_text
        record("AC7", bool(has_fields and shows_numbers), "mechanical",
               "debug_fields=%s visible_numbers=%s" % (has_fields, shows_numbers))

        # AC6 (mechanical part) ------------------------------------------------
        # Drive forward across the finish line WITHOUT the checkpoint, then
        # reverse back across it, then forward again. If the lap counter stays
        # at 1 the checkpoint + direction guard is really enforced.
        # Polling (not fixed durations) makes this robust to physics timing.
        def hold_until(key, predicate_js, timeout_ms):
            page.keyboard.down(key)
            deadline = time.time() + timeout_ms / 1000.0
            hit = False
            while time.time() < deadline:
                page.wait_for_timeout(50)
                if page.evaluate(predicate_js):
                    hit = True
                    break
            page.keyboard.up(key)
            page.wait_for_timeout(80)
            return hit

        page.goto(index.as_uri())
        page.wait_for_timeout(400)
        lap0 = page.evaluate("() => window.__racingDebug.lap")
        fwd1 = hold_until("ArrowUp", "() => window.__racingDebug.x > 485", 4000)
        x_after_fwd = page.evaluate("() => window.__racingDebug.x")
        rev = hold_until("ArrowDown", "() => window.__racingDebug.x < 475", 6000)
        x_after_rev = page.evaluate("() => window.__racingDebug.x")
        fwd2 = hold_until("ArrowUp", "() => window.__racingDebug.x > 485", 4000)
        ac6_state = page.evaluate("() => window.__racingDebug")
        crossed = bool(fwd1 and rev and fwd2)
        no_farm = ac6_state["lap"] == 1
        ac6_mech = bool(crossed and no_farm)

        # AC3 / AC4 / AC8 need a deterministic start --------------------------
        page.goto(index.as_uri())
        page.wait_for_timeout(400)
        d3pre = page.evaluate("() => window.__racingDebug")

        page.keyboard.down("ArrowUp")
        page.wait_for_timeout(1200)
        d3 = page.evaluate("() => window.__racingDebug")
        ok3 = bool(d3 and abs(d3["speed"]) > 20)
        record("AC3", ok3, "mechanical", "speed_state=%.1f" % (d3["speed"] if d3 else -1))

        # AC4 -----------------------------------------------------------------
        h_before = d3["heading"]
        page.keyboard.down("ArrowLeft")
        page.wait_for_timeout(700)
        d4 = page.evaluate("() => window.__racingDebug")
        page.keyboard.up("ArrowLeft")
        record("AC4", abs(d4["heading"] - h_before) > 0.05, "mechanical",
               "heading %.3f -> %.3f" % (h_before, d4["heading"]))

        # AC8 -----------------------------------------------------------------
        page.keyboard.down("ArrowRight")
        page.keyboard.down("ArrowUp")
        escaped = None
        for _ in range(40):
            page.wait_for_timeout(90)
            s = page.evaluate("() => window.__racingDebug")
            if s is None:
                continue
            samples.append([round(s["x"], 1), round(s["y"], 1)])
            if not (0 <= s["x"] <= CANVAS_W and 0 <= s["y"] <= CANVAS_H):
                escaped = (s["x"], s["y"])
                break
            sdf = page.evaluate(sdf_js(round(s["x"], 1), round(s["y"], 1)))
            if abs(sdf) > THW + 3:
                escaped = (round(s["x"], 1), round(s["y"], 1), round(sdf, 1))
                break
        page.keyboard.up("ArrowUp")
        page.keyboard.up("ArrowRight")
        record("AC8", escaped is None, "mechanical",
               "escaped=%s samples=%d max_sdf_ok" % (escaped, len(samples)))

        # AC9 -----------------------------------------------------------------
        ext = [u for u in bad_requests if not u.startswith("file://")]
        record("AC9", not bad_requests, "mechanical",
               "external_requests=%s total=%d" % (bad_requests[:5], len(requests)))

        browser.close()

    # AC6 is graded purely by the mechanical anti-farming probe above. No
    # identifier-based static markers are used, because the frozen spec never
    # pinned internal names and a name check would favour one arm's naming.
    record("AC6", ac6_mech, "mechanical",
           "forward_no_checkpoint=%s reverse=%s forward_again=%s lap0=%s "
           "x_fwd=%s x_rev=%s lap_end=%s"
           % (fwd1, rev, fwd2, lap0, round(x_after_fwd, 1),
              round(x_after_rev, 1), ac6_state["lap"]))

    return _emit(checks, args.json)


def _emit(checks, out_path):
    order = ["AC%d" % i for i in range(1, 11)]
    passed = sum(1 for c in order if checks.get(c, {}).get("pass"))
    payload = {"passed": passed, "total": len(order), "checks": {c: checks.get(c) for c in order}}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if out_path:
        pathlib.Path(out_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if passed == len(order) else 2


if __name__ == "__main__":
    sys.exit(main())
