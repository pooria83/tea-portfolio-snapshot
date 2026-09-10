#!/usr/bin/env bash
set -e

BATCH=${1:-5}
COOKIE_FILE=${2:-./cookies.txt}
CONCURRENCY=${3:-4}
LOG="scrape.log"
COUNTER=0

while true; do
  COUNTER=$((COUNTER + 1))
  echo "[Batch $COUNTER] Scraping next $BATCH products ..."
  uv run scripts/scrapers/run.py zara \
    --cookie-file "$COOKIE_FILE" \
    --concurrency "$CONCURRENCY" \
    --limit "$BATCH" 2>&1 | tee -a "$LOG"

  if command -v docker &>/dev/null; then
    PENDING=$(docker compose --profile minimal exec postgres \
      psql -U postgres -d product_graph -t -A \
      -c "SELECT COUNT(*) FROM public.scrape_products WHERE raw_data::jsonb = '{}'::jsonb;" 2>/dev/null || echo "?")
    echo "[Batch $COUNTER] Pending products remaining: $PENDING"
    if [ "$PENDING" = "0" ]; then
      echo "[Batch $COUNTER] All products scraped!"
      break
    fi
  else
    echo "[Batch $COUNTER] (skipping DB check — docker not available)"
  fi

  echo "[Batch $COUNTER] Sleeping 2 seconds before next batch ..."
  sleep 2
done

echo "Done. Total batches: $COUNTER"
