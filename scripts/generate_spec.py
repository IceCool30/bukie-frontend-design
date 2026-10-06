#!/usr/bin/env python3
"""Generate a frontend design spec from a feature description + brand reference.

Usage:
    generate_spec.py --feature "checkout page" \
                     --framework react-tailwind \
                     --brand brand.json \
                     --out design-spec.md

Stdlib only. Writes a markdown spec with Overview, Layout, Components (each with
default/hover/loading/error/empty states), Accessibility (WCAG 2.2 references),
Data, and Open Questions. Does NOT render or compile any UI.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path


VALID_FRAMEWORKS = ("react-tailwind", "vue", "plain-html")


def _die(msg: str, code: int = 1) -> None:
    sys.stderr.write(f"generate_spec.py: {msg}\n")
    sys.exit(code)


def _load_brand(path: Path) -> dict:
    if not path.is_file():
        _die(f"brand file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _die(f"brand file is not valid JSON: {e}")
    for k in ("primary_hex", "neutral_hex", "font_family", "base_spacing"):
        if k not in data:
            _die(f"brand file missing key '{k}'")
    return data


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "feature"


def _infer_components(feature: str) -> list[str]:
    """Pick a small starter set of components from the feature description.
    Keep it deterministic — no LLM call, just keyword sniffing."""
    f = feature.lower()
    out: list[str] = ["PageHeader", "PrimaryAction"]
    if any(w in f for w in ("checkout", "cart", "billing", "payment")):
        out += ["LineItemList", "OrderSummary", "PaymentForm"]
    if any(w in f for w in ("settings", "preference", "profile", "account")):
        out += ["SectionNav", "FieldRow", "SaveBar"]
    if any(w in f for w in ("dashboard", "metric", "analytic", "report")):
        out += ["MetricCard", "ChartPanel", "FilterBar"]
    if any(w in f for w in ("list", "table", "inbox", "feed")):
        out += ["DataTable", "EmptyState", "RowMenu"]
    if any(w in f for w in ("form", "signup", "login", "auth")):
        out += ["FormField", "InlineError", "SubmitButton"]
    if len(out) < 4:
        out += ["ContentCard", "EmptyState"]
    # Dedup while preserving order.
    seen: set[str] = set()
    uniq: list[str] = []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


STATES = ("default", "hover", "loading", "error", "empty")


def render_spec(feature: str, framework: str, brand: dict) -> str:
    today = dt.date.today().isoformat()
    components = _infer_components(feature)
    slug = _slugify(feature)

    lines: list[str] = []
    lines.append(f"# Design Spec — {feature.strip().title()}")
    lines.append("")
    lines.append(f"- **Slug**: `{slug}`")
    lines.append(f"- **Framework**: `{framework}`")
    lines.append(f"- **Generated**: {today}")
    lines.append(f"- **Brand primary**: `{brand['primary_hex']}`")
    lines.append(f"- **Brand neutral**: `{brand['neutral_hex']}`")
    lines.append(f"- **Font family**: `{brand['font_family']}`")
    lines.append(f"- **Base spacing unit**: `{brand['base_spacing']}px`")
    lines.append("")

    lines.append("## Overview")
    lines.append("")
    lines.append(
        f"Surface: **{feature.strip()}**. Target framework: `{framework}`. "
        "This spec is the contract between design and engineering — it pins down the layout, "
        "the component breakdown, the state matrix, and the accessibility floor before any code is written."
    )
    lines.append("")

    lines.append("## Layout")
    lines.append("")
    lines.append("- Top region: page header + primary action")
    lines.append("- Main region: content stack (cards / form / table per the components below)")
    lines.append("- Side region (optional): nav or filter rail; collapses below 768px")
    lines.append("- Bottom region: persistent action bar (only if the surface has a save / submit step)")
    lines.append("- Container max-width: 1200px; gutter: `spacing.6` (24px at base 4)")
    lines.append("")

    lines.append("## Components")
    lines.append("")
    lines.append("Each component below ships **all five states**. Skipping a state is a review-blocker.")
    lines.append("")
    for c in components:
        lines.append(f"### {c}")
        lines.append("")
        lines.append("| State | Spec |")
        lines.append("|---|---|")
        for s in STATES:
            lines.append(f"| `{s}` | {_state_hint(c, s)} |")
        lines.append("")

    lines.append("## Accessibility")
    lines.append("")
    lines.append("Target: **WCAG 2.2 Level AA**. Reference: https://www.w3.org/TR/WCAG22/")
    lines.append("")
    lines.append("- **Focus order**: matches DOM order; primary action is the last reachable in each section (SC 2.4.3)")
    lines.append("- **Visible focus**: 2px outline at `color.brand.500`, offset 2px (SC 2.4.7)")
    lines.append("- **Color contrast**: body text against background ≥ 4.5:1; large text ≥ 3:1 (SC 1.4.3)")
    lines.append("- **ARIA roles**: buttons use `<button>`; menus use `role=\"menu\"`; live regions for inline errors use `aria-live=\"polite\"`")
    lines.append("- **Keyboard**: every interactive element reachable via Tab; Esc dismisses modals; Enter activates the focused button (SC 2.1.1)")
    lines.append("- **Reduced motion**: honor `prefers-reduced-motion: reduce` — disable non-essential transitions")
    lines.append("")

    lines.append("## Data")
    lines.append("")
    lines.append("- List the API endpoints / queries that hydrate each component above")
    lines.append("- For each: shape (GET/POST), response schema link, loading-state owner (server / client)")
    lines.append("- Empty state copy: write it here so engineering doesn't ship `\"No data\"`")
    lines.append("")

    lines.append("## Open Questions")
    lines.append("")
    lines.append("- Does the primary brand color clear AA against the neutral surface? Run a contrast check.")
    lines.append("- Is the side-region collapse threshold (768px) right for the target users?")
    lines.append("- Which empty-state illustration set are we using? Link it here.")
    lines.append("- Are there RTL languages in scope? If yes, every layout note above needs a mirror plan.")
    lines.append("")

    return "\n".join(lines) + "\n"


def _state_hint(component: str, state: str) -> str:
    base = {
        "default": "resting style; no user interaction",
        "hover": "cursor over; raise elevation 1 step or shift bg 1 ramp step",
        "loading": "skeleton placeholder; disable actions; aria-busy=\"true\"",
        "error": "inline message; red border; preserves user input",
        "empty": "illustration + one-line copy + primary CTA to seed data",
    }
    return base.get(state, "TBD")


def main() -> int:
    p = argparse.ArgumentParser(description="Generate a frontend design spec.")
    p.add_argument("--feature", required=True, help="one-sentence feature description")
    p.add_argument("--framework", default="react-tailwind", choices=VALID_FRAMEWORKS)
    p.add_argument("--brand", required=True, type=Path, help="path to brand.json")
    p.add_argument("--out", required=True, type=Path, help="output markdown path")
    args = p.parse_args()

    brand = _load_brand(args.brand)
    spec = render_spec(args.feature, args.framework, brand)

    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(spec, encoding="utf-8")
    print(f"wrote {out} ({len(spec.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
