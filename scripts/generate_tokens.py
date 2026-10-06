#!/usr/bin/env python3
"""Generate a W3C-shaped design-tokens JSON from a brand reference.

Usage:
    generate_tokens.py --brand brand.json --out tokens.json

Stdlib only. Reads `primary_hex`, `neutral_hex`, `font_family`, `base_spacing`
from a brand JSON, then computes:

  color.brand.{50..900}   — HSL lightness ramp from primary_hex
  color.neutral.{50..900} — HSL lightness ramp from neutral_hex
  spacing.{0..12}         — multiples of base_spacing
  radius.{sm,md,lg,full}
  typography.{display,heading,body,mono}

Token shape follows the W3C Design Tokens Community Group draft:
https://tr.designtokens.org/format/
"""

from __future__ import annotations

import argparse
import colorsys
import json
import re
import sys
from pathlib import Path


HEX_RE = re.compile(r"^#([0-9a-fA-F]{6})$")
RAMP_STOPS = (50, 100, 200, 300, 400, 500, 600, 700, 800, 900)
# Lightness target per stop (0..1). 50 is near-white, 900 near-black.
# These are tuned for a perceptually flat ramp; not copied from any vendor.
LIGHTNESS_BY_STOP = {
    50: 0.97,
    100: 0.93,
    200: 0.86,
    300: 0.76,
    400: 0.64,
    500: 0.52,
    600: 0.44,
    700: 0.34,
    800: 0.24,
    900: 0.14,
}


def _die(msg: str, code: int = 1) -> None:
    sys.stderr.write(f"generate_tokens.py: {msg}\n")
    sys.exit(code)


def _load_brand(path: Path) -> dict:
    if not path.is_file():
        _die(f"brand file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _die(f"brand file not valid JSON: {e}")
    for k in ("primary_hex", "neutral_hex", "font_family", "base_spacing"):
        if k not in data:
            _die(f"brand file missing key '{k}'")
    if not HEX_RE.match(data["primary_hex"]):
        _die(f"primary_hex must be '#RRGGBB', got {data['primary_hex']!r}")
    if not HEX_RE.match(data["neutral_hex"]):
        _die(f"neutral_hex must be '#RRGGBB', got {data['neutral_hex']!r}")
    if not isinstance(data["base_spacing"], int) or data["base_spacing"] <= 0:
        _die(f"base_spacing must be a positive int, got {data['base_spacing']!r}")
    return data


def _hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return (
        int(h[0:2], 16) / 255.0,
        int(h[2:4], 16) / 255.0,
        int(h[4:6], 16) / 255.0,
    )


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    def to8(x: float) -> int:
        return max(0, min(255, round(x * 255)))
    return f"#{to8(r):02X}{to8(g):02X}{to8(b):02X}"


def build_ramp(seed_hex: str) -> dict:
    """Build a 50..900 color ramp from a seed hex by holding hue/saturation
    constant and walking lightness across the stop table. Pure Python."""
    r, g, b = _hex_to_rgb(seed_hex)
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    # For very dark seeds (neutrals), boost saturation floor so the ramp
    # doesn't collapse to grey at the light end.
    s_floor = max(s, 0.06)
    ramp: dict = {}
    for stop in RAMP_STOPS:
        target_l = LIGHTNESS_BY_STOP[stop]
        nr, ng, nb = colorsys.hls_to_rgb(h, target_l, s_floor)
        ramp[str(stop)] = {
            "value": _rgb_to_hex(nr, ng, nb),
            "type": "color",
        }
    return ramp


def build_spacing(base: int) -> dict:
    out: dict = {}
    for i in range(0, 13):
        out[str(i)] = {"value": f"{i * base}px", "type": "dimension"}
    return out


def build_radius(base: int) -> dict:
    # Independent of base spacing's exact value — radius scale is fixed.
    return {
        "sm": {"value": "4px", "type": "dimension"},
        "md": {"value": "8px", "type": "dimension"},
        "lg": {"value": "16px", "type": "dimension"},
        "full": {"value": "9999px", "type": "dimension"},
    }


def build_typography(font_family: str) -> dict:
    def style(size: str, weight: str, lh: str) -> dict:
        return {
            "value": {
                "fontFamily": font_family,
                "fontSize": size,
                "fontWeight": weight,
                "lineHeight": lh,
            },
            "type": "typography",
        }
    return {
        "display": style("48px", "700", "1.1"),
        "heading": style("24px", "600", "1.25"),
        "body": style("16px", "400", "1.5"),
        "mono": {
            "value": {
                "fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace",
                "fontSize": "14px",
                "fontWeight": "400",
                "lineHeight": "1.5",
            },
            "type": "typography",
        },
    }


def build_tokens(brand: dict) -> dict:
    return {
        "$schema": "https://tr.designtokens.org/format/",
        "color": {
            "brand": build_ramp(brand["primary_hex"]),
            "neutral": build_ramp(brand["neutral_hex"]),
        },
        "spacing": build_spacing(int(brand["base_spacing"])),
        "radius": build_radius(int(brand["base_spacing"])),
        "typography": build_typography(brand["font_family"]),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Generate W3C design tokens JSON from a brand reference.")
    p.add_argument("--brand", required=True, type=Path, help="brand.json input")
    p.add_argument("--out", required=True, type=Path, help="tokens.json output")
    args = p.parse_args()

    brand = _load_brand(args.brand)
    tokens = build_tokens(brand)

    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(tokens, indent=2) + "\n", encoding="utf-8")
    n_colors = len(tokens["color"]["brand"]) + len(tokens["color"]["neutral"])
    print(f"wrote {out} ({n_colors} color tokens, {len(tokens['spacing'])} spacing stops)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
