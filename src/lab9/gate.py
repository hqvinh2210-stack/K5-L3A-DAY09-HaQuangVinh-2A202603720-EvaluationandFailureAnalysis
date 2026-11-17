"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    metrics = pr.get("metrics")
    if not isinstance(metrics, dict):
        problems.append("PR metrics is not an object")
        metrics = {}
    for metric_id, value in metrics.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isfinite(value):
            problems.append(f"metric {metric_id} is not finite")

    manifest = pr.get("manifest") or {}
    rows = pr.get("rows")
    if not isinstance(rows, list):
        problems.append("PR rows is not a list")
        rows = []
    items = manifest.get("items")
    seeds = manifest.get("seeds")
    if not isinstance(items, int) or items < 0 or not isinstance(seeds, list) or len(set(seeds)) != len(seeds):
        problems.append("manifest has invalid items or seeds")
    else:
        expected_count = items * len(seeds)
        if len(rows) != expected_count:
            problems.append(f"row count {len(rows)} != manifest {items} x {len(seeds)} = {expected_count}")

    def row_key(row: dict) -> tuple[object, object]:
        return row.get("item_id"), row.get("seed")

    pr_keys = [row_key(row) for row in rows if isinstance(row, dict)]
    if len(pr_keys) != len(set(pr_keys)):
        problems.append("PR contains duplicate (item_id, seed) rows")
    base_rows = base.get("rows") if isinstance(base.get("rows"), list) else []
    base_keys = [row_key(row) for row in base_rows if isinstance(row, dict)]
    if set(pr_keys) != set(base_keys):
        problems.append("PR (item_id, seed) set differs from baseline")
    if isinstance(items, int) and len({item for item, _ in pr_keys}) != items:
        problems.append("manifest item count differs from rows")
    if isinstance(seeds, list) and {seed for _, seed in pr_keys} != set(seeds):
        problems.append("manifest seed set differs from rows")

    if pr.get("evaluator_failures"):
        problems.append("PR contains evaluator failures")
    graded = [m["id"] for m in spec.get("metrics", []) if m.get("id") in GRADERS]
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(f"row {index} is not an object")
            continue
        for metric_id in graded:
            if row.get(metric_id) is None:
                problems.append(f"row {row_key(row)} has missing {metric_id}")

    base_by_key = {row_key(row): row for row in base_rows if isinstance(row, dict)}
    for row in rows:
        if not isinstance(row, dict) or row_key(row) not in base_by_key:
            continue
        current_slices = sorted(set(row.get("slices") or []))
        baseline_slices = sorted(set(base_by_key[row_key(row)].get("slices") or []))
        if current_slices != baseline_slices:
            problems.append(f"row {row_key(row)} slice tags differ from baseline")

    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        def ratchet(current_entries: list[dict], baseline_entries: list[dict], label: str,
                    key_fields: tuple[str, ...]) -> None:
            current = {tuple(entry.get(k) for k in key_fields): entry for entry in current_entries}
            for key, old in {tuple(entry.get(k) for k in key_fields): entry for entry in baseline_entries}.items():
                name = "/".join(str(part) for part in key)
                new = current.get(key)
                if new is None:
                    problems.append(f"{label} {name} was removed")
                    continue
                if old.get("blocking") and not new.get("blocking"):
                    problems.append(f"{label} {name} changed from blocking to non-blocking")
                old_th, new_th = old.get("threshold", old), new.get("threshold", new)
                if "min" in old_th and ("min" not in new_th or new_th["min"] < old_th["min"]):
                    problems.append(f"{label} {name} loosened min")
                if "max" in old_th and ("max" not in new_th or new_th["max"] > old_th["max"]):
                    problems.append(f"{label} {name} loosened max")
                if "max_increase" in old_th and (
                    "max_increase" not in new_th or new_th["max_increase"] > old_th["max_increase"]
                ):
                    problems.append(f"{label} {name} loosened max_increase")
                if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
                    problems.append(f"{label} {name} removed no_significant_drop")

        ratchet(spec.get("metrics", []), base_spec.get("metrics", []), "metric", ("id",))
        ratchet(spec.get("slices", []), base_spec.get("slices", []), "slice", ("name", "metric"))
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bootstrap = spec.get("bootstrap", {})
    for slice_spec in spec.get("slices", []):
        name = slice_spec["name"]
        metric = slice_spec["metric"]
        threshold = {k: slice_spec[k] for k in ("min", "no_significant_drop") if k in slice_spec}
        current = per_item(pr, metric, slice_name=name)
        baseline = per_item(base, metric, slice_name=name)
        value = sum(current.values()) / len(current) if current else None
        verdict, note = "ok", ""
        if value is None:
            verdict = "missing"
        elif "min" in threshold and value < threshold["min"]:
            verdict = "fail"
        if threshold.get("no_significant_drop") and current and baseline:
            keys = sorted(set(current) & set(baseline))
            if keys:
                delta, low, high = stats.paired_bootstrap(
                    [current[key] for key in keys], [baseline[key] for key in keys],
                    n_resamples=bootstrap.get("n_resamples", 1000),
                    rng=bootstrap.get("rng", 2027),
                    confidence=bootstrap.get("confidence", 0.95),
                )
                note = f"Δ {delta:+.3f} CI [{low:+.3f}, {high:+.3f}]"
                if high < 0:
                    verdict = "fail"
        slice_id = f"slice:{name}/{metric}"
        if verdict != "ok" and slice_spec.get("blocking"):
            blocked.append(slice_id)
        label = {"ok": "ok", "missing": "MISSING"}.get(
            verdict, "BLOCK" if slice_spec.get("blocking") else "warn"
        )
        shown = "None" if value is None else f"{value:.4f}"
        lines.append(f"  {slice_id:<22} {shown:<8} {json.dumps(threshold):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
