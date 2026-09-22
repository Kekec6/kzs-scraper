#!/usr/bin/env bash
# Po lokalnem scrapu: commit HTML/data in push (sproži Deploy Pages).
set -euo pipefail
cd "$(dirname "$0")/.."

git add data/ output/html/
if git diff --staged --quiet; then
  echo "Ni sprememb za commit."
  exit 0
fi

git commit -m "chore: scrape update $(date -u +%Y-%m-%dT%H:%MZ)"
git push
echo "OK – po pushu se zažene Deploy Pages."
