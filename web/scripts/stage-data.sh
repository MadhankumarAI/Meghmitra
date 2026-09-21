#!/usr/bin/env bash
# Prepare web/public/data for deployment:   npm run data:stage
# Go back to live pipeline data:            npm run data:link
#
# Day to day, public/data is a Windows junction to D:\Morphy\exports. Vercel can't
# upload a link reliably, its Hobby plan caps an upload at 100 MB, and the exports hold
# files the public site must not serve (contract/, forecast/latest.json). This swaps
# the junction for a real folder with only what the site reads, gzipping the daily
# forecast and advisory files (the app unpacks them itself: src/lib/gz.ts).
# Reads from D: only; nothing on D: is modified.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${MORPHY_EXPORTS:-/d/Morphy/exports}"
YEAR="${YEAR:-2023}"
DEST="public/data"

[ -f "$SRC/blocks_index.json" ] || { echo "error: $SRC not found. Is the D: drive connected?" >&2; exit 1; }

rm -rf "$DEST.tmp"
mkdir -p "$DEST.tmp/forecast" "$DEST.tmp/advisory" "$DEST.tmp/explain"
# Village and panchayat data. The outlines are a few hundred MB, which a static host will not
# take, so they stay out of a deployment unless VILLAGE_GEOM=1 says otherwise. Search, the map
# points and the per-village adjustments are small and always go.
mkdir -p "$DEST.tmp/villages"
cp "$SRC/villages/"*.json "$DEST.tmp/villages/" 2>/dev/null || true
cp -r "$SRC/villages/cells" "$SRC/villages/clim" "$DEST.tmp/villages/" 2>/dev/null || true
[ "${VILLAGE_GEOM:-0}" = "1" ] && cp -r "$SRC/villages/geom" "$DEST.tmp/villages/" 2>/dev/null || true
cp "$SRC/india.pmtiles" "$SRC/blocks_index.json" "$SRC/crops.json" "$SRC/metrics.json" "$DEST.tmp/"
cp "$SRC/advice_skill_$YEAR.json" "$SRC/model_card.json" "$SRC/experiments.json" "$DEST.tmp/" 2>/dev/null || true
cp "$SRC/forecast/season_$YEAR.json" "$DEST.tmp/forecast/"
n=0
for kind in forecast advisory explain; do
  for f in "$SRC/$kind/$YEAR"-*.json "$SRC/$kind/live.json"; do
    [ -f "$f" ] || continue
    gzip -9 -c "$f" > "$DEST.tmp/$kind/$(basename "$f").gz"
    n=$((n + 1))
  done
done
[ -f "$SRC/forecast/live_status.json" ] && cp "$SRC/forecast/live_status.json" "$DEST.tmp/forecast/"
# atmosphere frames for "Understand" (already gzipped) and the live GFS index
if [ -d "$SRC/atmos" ]; then
  mkdir -p "$DEST.tmp/atmos"
  cp "$SRC/atmos/"era5_"$YEAR"-*.json.gz "$SRC/atmos/"gfs_*.json.gz "$SRC/atmos/orography.json.gz" "$DEST.tmp/atmos/" 2>/dev/null || true
  cp "$SRC/atmos/live_index.json" "$DEST.tmp/atmos/" 2>/dev/null || true
fi

# remove the junction itself (rmdir on a junction never touches its target), then swap in
if [ -e "$DEST" ] || [ -L "$DEST" ]; then
  if cmd //c "dir /al public" 2>/dev/null | grep -q "<JUNCTION>.*data"; then
    cmd //c "rmdir public\\data"
  else
    rm -rf "$DEST"
  fi
fi
mv "$DEST.tmp" "$DEST"
echo "staged $n daily files + map + index into $DEST: $(du -sh "$DEST" | cut -f1)"
echo "deploy now; afterwards run: npm run data:link"
