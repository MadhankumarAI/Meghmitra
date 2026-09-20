#!/usr/bin/env bash
# Point web/public/data back at the live pipeline exports on D: (undoes data:stage).
set -euo pipefail
cd "$(dirname "$0")/.."
if cmd //c "dir /al public" 2>/dev/null | grep -q "<JUNCTION>.*data"; then
  echo "public/data is already linked"; exit 0
fi
rm -rf public/data
cmd //c "mklink /J public\\data D:\\Morphy\\exports" >/dev/null
echo "public/data -> D:\\Morphy\\exports"
