#!/bin/sh
# Run the checker over each example file and show the result.
# The flagged examples fail on purpose, so each run is allowed to fail.
cd "$(dirname "$0")/.."
for f in examples/clean.csv examples/flagged.csv examples/edge.csv examples/utf16.csv; do
  echo "== $f =="
  python3 src/csv_bom_checker.py "$f" || true
  echo
done
echo "== examples/ : the whole folder =="
python3 src/csv_bom_checker.py examples/ || true
