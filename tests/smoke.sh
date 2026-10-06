#!/usr/bin/env bash
# Smoke test for frontend-design. Runs offline: feeds the fixture brand.json
# through generate_spec -> generate_tokens -> export_figma_schema and checks
# the artifacts have the expected shape.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cp "$HERE/fixtures/brand.json" "$TMP/brand.json"

# 1. Spec
python3 "$ROOT/scripts/generate_spec.py" \
  --feature "checkout page" \
  --framework react-tailwind \
  --brand "$TMP/brand.json" \
  --out "$TMP/design-spec.md"
test -f "$TMP/design-spec.md"

for h in "## Overview" "## Layout" "## Components" "## Accessibility" "## Data" "## Open Questions"; do
  if ! grep -qF "$h" "$TMP/design-spec.md"; then
    echo "FAIL: missing header '$h' in design-spec.md" >&2
    exit 1
  fi
done

# Spec must reference all five states and at least one inferred component.
for s in default hover loading error empty; do
  if ! grep -qF "\`$s\`" "$TMP/design-spec.md"; then
    echo "FAIL: missing state '$s' in design-spec.md" >&2
    exit 1
  fi
done
if ! grep -qF "OrderSummary" "$TMP/design-spec.md"; then
  echo "FAIL: checkout-feature component 'OrderSummary' not inferred" >&2
  exit 1
fi

# 2. Tokens
python3 "$ROOT/scripts/generate_tokens.py" \
  --brand "$TMP/brand.json" \
  --out "$TMP/tokens.json"
test -f "$TMP/tokens.json"

grep -q '"color"' "$TMP/tokens.json"
grep -q '"brand"' "$TMP/tokens.json"
grep -q '"500"' "$TMP/tokens.json"
grep -q '"spacing"' "$TMP/tokens.json"
grep -q '"radius"' "$TMP/tokens.json"
grep -q '"typography"' "$TMP/tokens.json"

# Tokens JSON must parse and have brand 50..900.
python3 - "$TMP/tokens.json" <<'PY'
import json, sys
t = json.loads(open(sys.argv[1]).read())
stops = set(t["color"]["brand"].keys())
needed = {"50","100","200","300","400","500","600","700","800","900"}
assert needed.issubset(stops), f"missing brand stops: {needed - stops}"
assert len(t["spacing"]) == 13, f"spacing must have 13 stops, got {len(t['spacing'])}"
assert t["typography"]["body"]["value"]["fontFamily"] == "Inter"
PY

# 3. Figma schema
python3 "$ROOT/scripts/export_figma_schema.py" \
  --spec "$TMP/design-spec.md" \
  --tokens "$TMP/tokens.json" \
  --out "$TMP/figma-schema.json"
test -f "$TMP/figma-schema.json"

grep -q '"frames"' "$TMP/figma-schema.json"
grep -q '"schemaVersion"' "$TMP/figma-schema.json"

python3 - "$TMP/figma-schema.json" <<'PY'
import json, sys
s = json.loads(open(sys.argv[1]).read())
assert len(s["frames"]) >= 4, f"expected >=4 component frames, got {len(s['frames'])}"
for fr in s["frames"]:
    children = fr["children"]
    states = {c["name"].split("/")[-1] for c in children}
    assert states == {"default","hover","loading","error","empty"}, f"bad states in {fr['name']}: {states}"
PY

# 4. Reject invalid hex (negative path).
echo '{"primary_hex":"red","neutral_hex":"#0F172A","font_family":"Inter","base_spacing":4}' > "$TMP/bad.json"
if python3 "$ROOT/scripts/generate_tokens.py" --brand "$TMP/bad.json" --out "$TMP/should-not-exist.json" >/dev/null 2>&1; then
  echo "FAIL: generate_tokens.py accepted invalid hex" >&2
  exit 1
fi

echo "OK: frontend-design smoke test passed"
