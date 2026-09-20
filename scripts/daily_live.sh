#!/usr/bin/env bash
# One command for the daily live run (Git Bash on the laptop, D: connected):
#
#   bash scripts/daily_live.sh            fetch, compute, pull to D:
#   bash scripts/daily_live.sh --deploy   ...and publish to Vercel
#
# Why the laptop is in the loop: imdpune.gov.in (IMD real-time rainfall) is reachable from
# the laptop but not from the server. Everything heavy runs on the server.
set -euo pipefail
cd "$(dirname "$0")/.."
SERVER="user02@14.143.127.114"
YEAR=$(date +%Y)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)
PY=".venv/Scripts/python"
export PYTHONIOENCODING=utf-8

echo "== 1/4 IMD real-time rainfall to $YESTERDAY (laptop)"
"$PY" src/data/download_imd_rt.py "$YEAR-05-01" "$YESTERDAY"

echo "== 2/4 upload new days to the server"
ssh -o BatchMode=yes "$SERVER" "mkdir -p ~/morphy/data/raw/imd_rt"
scp -q -o BatchMode=yes D:/Morphy/raw/imd_rt/rain_ind0.25_"${YEAR:2:2}"_*.grd "$SERVER:morphy/data/raw/imd_rt/"

echo "== 3/4 live outlook + NOAA GFS atmosphere (server)"
ssh -o BatchMode=yes "$SERVER" 'source ~/morphy/env.sh && cd ~/morphy \
  && (python src/live/run_live.py || echo "live outlook not published (see live_status.json)") \
  && python src/atmos/frames.py gfs \
  && python src/export/model_card.py \
  && python src/export/experiments_json.py' 2>&1 | grep -v NVML | tail -6

echo "== 4/4 pull results to D:"
TODAY=$(date +%Y-%m-%d)
mkdir -p D:/Morphy/exports/forecast D:/Morphy/exports/advisory D:/Morphy/exports/atmos D:/Morphy/exports/explain
scp -q -o BatchMode=yes "$SERVER:morphy/data/exports/forecast/live_status.json" D:/Morphy/exports/forecast/
scp -q -o BatchMode=yes "$SERVER:morphy/data/exports/forecast/live.json" "$SERVER:morphy/data/exports/forecast/$TODAY.json" \
    D:/Morphy/exports/forecast/ 2>/dev/null || true
scp -q -o BatchMode=yes "$SERVER:morphy/data/exports/advisory/live.json" "$SERVER:morphy/data/exports/advisory/$TODAY.json" \
    D:/Morphy/exports/advisory/ 2>/dev/null || true
scp -q -o BatchMode=yes "$SERVER:morphy/data/exports/explain/live.json" "$SERVER:morphy/data/exports/explain/$TODAY.json" \
    D:/Morphy/exports/explain/ 2>/dev/null || true
scp -q -o BatchMode=yes "$SERVER:morphy/data/exports/model_card.json" "$SERVER:morphy/data/exports/experiments.json" D:/Morphy/exports/
scp -q -o BatchMode=yes "$SERVER:morphy/data/exports/atmos/gfs_*" "$SERVER:morphy/data/exports/atmos/live_index.json" \
    D:/Morphy/exports/atmos/
cat D:/Morphy/exports/forecast/live_status.json; echo

# The WhatsApp service (act_1/) answers "Next 4 weeks" from its latest.json (it re-reads on change),
# and its officers approve today's advisories in the console (Review & send).
ACT="act_1"
if [ -f "D:/Morphy/exports/forecast/$TODAY.json" ] && [ -d "$ACT/forecast" ]; then
  echo "== hand today's outlook to the WhatsApp service"
  MORPHY_EXPORTS=D:/Morphy/exports "$PY" src/export/advisory_contract.py "$TODAY" --latest "$ACT/forecast/latest.json"
fi

if [ "${1:-}" = "--deploy" ]; then
  echo "== deploy"
  (cd web && npm run data:stage && npx vercel --prod --yes && npm run data:link)
fi
echo "done"
