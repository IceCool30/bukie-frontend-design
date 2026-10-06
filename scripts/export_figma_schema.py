#!/usr/bin/env python3
"""Export a Figma frame schema from a design-spec.md + tokens.json.

Usage:
    export_figma_schema.py --spec design-spec.md \
                           --tokens tokens.json \
                           --out figma-schema.json

Stdlib only. Parses the spec's `### <Component>` headings and the token names,
then emits a JSON describing Figma frames (one per component, one nested frame
per state) a designer can drop into a Figma bulk-create plugin. No Figma API
calls — this is a portable schema, not a Figma file.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path


STATES = ("default", "hover", "loading", "error", "empty")

# Frame size per state. Tuned for "card-shaped" components; designer adjusts.
DEFAULT_FRAME = {"width": 360, "height": 240}


def _die(msg: str, code: int = 1) -> None:
    sys.stderr.write(f"export_figma_schema.py: {msg}\n")
    sys.exit(code)


def _read_spec(path: Path) -> str:
    if not path.is_file():
        _die(f"spec file not found: {path}")
    return path.read_text(encoding="utf-8")


def _read_tokens(path: Path) -> dict:
    if not path.is_file():
        _die(f"tokens file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _die(f"tokens file not valid JSON: {e}")
    return {}  # unreachable


def parse_components(spec_text: str) -> list[str]:
    """Pull every `### <Name>` heading under the `## Components` section."""
    out: list[str] = []
    in_components = False
    for line in spec_text.splitlines():
        if line.startswith("## "):
            in_components = line.strip().lower().startswith("## components")
            continue
        if in_components and line.startswith("### "):
            name = line[4:].strip()
            if name:
                out.append(name)
    return out


def primary_color(tokens: dict) -> str:
    try:
        return tokens["color"]["brand"]["500"]["value"]
    except (KeyError, TypeError):
        return "#3B82F6"


def neutral_bg(tokens: dict) -> str:
    try:
        return tokens["color"]["neutral"]["50"]["value"]
    except (KeyError, TypeError):
        return "#F8FAFC"


def font_family(tokens: dict) -> str:
    try:
        return tokens["typography"]["body"]["value"]["fontFamily"]
    except (KeyError, TypeError):
        return "Inter"


def build_schema(components: list[str], tokens: dict) -> dict:
    brand = primary_color(tokens)
    bg = neutral_bg(tokens)
    font = font_family(tokens)
    frames: list[dict] = []
    for comp in components:
        children: list[dict] = []
        for i, state in enumerate(STATES):
            children.append({
                "name": f"{comp}/{state}",
                "type": "FRAME",
                "x": i * (DEFAULT_FRAME["width"] + 24),
                "y": 0,
                "width": DEFAULT_FRAME["width"],
                "height": DEFAULT_FRAME["height"],
                "background": bg,
                "stroke": brand if state == "default" else None,
                "notes": f"State: {state}",
            })
        frames.append({
            "name": comp,
            "type": "FRAME",
            "layoutMode": "HORIZONTAL",
            "itemSpacing": 24,
            "padding": 16,
            "children": children,
        })
    return {
        "schemaVersion": "1.0",
        "generatedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tokenRefs": {
            "brand500": brand,
            "neutral50": bg,
            "fontFamily": font,
        },
        "frames": frames,
        "notes": [
            "Drop this JSON into a Figma bulk-create plugin (e.g., one that consumes a frames[] array).",
            "Each component frame holds one nested frame per state. Replace placeholder colors with token references inside Figma.",
            "This file is a portable schema; it is not a .fig file and does not call the Figma API.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Export a Figma frame schema from a design spec + tokens.")
    p.add_argument("--spec", required=True, type=Path, help="design-spec.md input")
    p.add_argument("--tokens", required=True, type=Path, help="tokens.json input")
    p.add_argument("--out", required=True, type=Path, help="figma-schema.json output")
    args = p.parse_args()

    spec_text = _read_spec(args.spec)
    tokens = _read_tokens(args.tokens)
    components = parse_components(spec_text)
    if not components:
        _die("no '### <Component>' headings found under '## Components' in the spec")

    schema = build_schema(components, tokens)

    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(components)} components, {len(components) * len(STATES)} frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
