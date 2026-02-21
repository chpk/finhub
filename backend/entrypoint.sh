#!/bin/bash
set -e

echo "============================================"
echo "  NFRA Compliance Engine — Backend Startup"
echo "============================================"

# Check if ChromaDB has been indexed by looking for the SQLite database
# that grows beyond a minimal size when collections have data.
CHROMA_DB="${CHROMA_PERSIST_DIR:-./chroma_db}/chroma.sqlite3"
NEEDS_INDEX=false

if [ ! -f "$CHROMA_DB" ]; then
    NEEDS_INDEX=true
    echo "[startup] No ChromaDB database found — first-run indexing required."
elif [ "$(stat -c%s "$CHROMA_DB" 2>/dev/null || echo 0)" -lt 100000 ]; then
    NEEDS_INDEX=true
    echo "[startup] ChromaDB database is nearly empty — indexing required."
else
    echo "[startup] ChromaDB database found ($(du -h "$CHROMA_DB" | cut -f1)). Skipping pre-flight indexing."
fi

if [ "$NEEDS_INDEX" = true ] && [ -d "data/compliance_rules" ]; then
    PDF_COUNT=$(find data/compliance_rules -name "*.pdf" 2>/dev/null | wc -l)
    if [ "$PDF_COUNT" -gt 0 ]; then
        echo "[startup] Found $PDF_COUNT compliance rule PDFs."
        echo "[startup] Running first-run indexing (this may take several minutes)..."
        export COMPLIANCE_RULES_DIR=data/compliance_rules
        python -m scripts.index_compliance_rules || {
            echo "[startup] WARNING: Pre-flight indexing failed. The app will"
            echo "         retry via AUTO_INDEX_ON_STARTUP during FastAPI startup."
        }
    else
        echo "[startup] No PDFs found in data/compliance_rules/ — skipping."
    fi
fi

echo "[startup] Starting uvicorn..."
exec uvicorn app.main:app \
    --host "${BACKEND_HOST:-0.0.0.0}" \
    --port "${BACKEND_PORT:-8888}"
