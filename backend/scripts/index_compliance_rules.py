"""Index all compliance rules PDFs into ChromaDB for retrieval.

Usage:
    cd backend
    python -m scripts.index_compliance_rules

Processes all PDFs in the compliance rules directory, extracts text/tables
using Unstructured.io, chunks them, generates embeddings (text-embedding-3-large),
and stores them in the appropriate ChromaDB collection.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Ensure the backend package is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.utils.chunking import ComplianceChunker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("index_compliance_rules")

# Map folder names → framework metadata tag + ChromaDB collection
FOLDER_MAP: dict[str, dict[str, str]] = {
    "Auditing_Standards":    {"framework": "Auditing_Standards",    "collection": "regulatory_frameworks"},
    "Disclosure_Checklists": {"framework": "Disclosure_Checklists", "collection": "disclosure_checklists"},
    "ESG_BRSR":              {"framework": "ESG_BRSR",              "collection": "regulatory_frameworks"},
    "IndAS_Standards":       {"framework": "IndAS",                 "collection": "regulatory_frameworks"},
    "RBI_Norms":             {"framework": "RBI_Norms",             "collection": "regulatory_frameworks"},
    "Schedule_III":          {"framework": "Schedule_III",          "collection": "regulatory_frameworks"},
    "SEBI_LODR":             {"framework": "SEBI_LODR",             "collection": "regulatory_frameworks"},
}

def _resolve_default_rules_dir() -> Path:
    """Find the compliance rules directory relative to the backend root.

    Checks (in order):
    1. ``./data/compliance_rules``  (standard location, works in Docker)
    2. ``../NFRA_Challenge_Data/01_Compliance_Rules``  (repo-level data)
    """
    candidates = [
        Path("data/compliance_rules"),
        Path(__file__).resolve().parent.parent / "data" / "compliance_rules",
        Path(__file__).resolve().parent.parent.parent / "NFRA_Challenge_Data" / "01_Compliance_Rules",
    ]
    for p in candidates:
        if p.is_dir():
            return p
    return candidates[0]


COMPLIANCE_RULES_DIR = Path(
    os.environ.get("COMPLIANCE_RULES_DIR", "")
) if os.environ.get("COMPLIANCE_RULES_DIR") else _resolve_default_rules_dir()

# Embedding batch size (tokens budget friendly)
EMBED_BATCH = 50


async def index_all() -> None:
    settings = get_settings()

    processor = DocumentProcessor(
        api_key=settings.UNSTRUCTURED_API_KEY,
        api_url=settings.UNSTRUCTURED_API_URL,
    )
    embedder = EmbeddingService(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    vector_store = VectorStoreService(persist_dir=settings.CHROMA_PERSIST_DIR)
    chunker = ComplianceChunker(chunk_size=1200, chunk_overlap=200)

    if not COMPLIANCE_RULES_DIR.is_dir():
        logger.error("Compliance rules directory not found: %s", COMPLIANCE_RULES_DIR)
        return

    total_chunks = 0
    total_files = 0
    t0 = time.perf_counter()

    for folder_name, mapping in FOLDER_MAP.items():
        folder_path = COMPLIANCE_RULES_DIR / folder_name
        if not folder_path.is_dir():
            logger.warning("Folder not found, skipping: %s", folder_path)
            continue

        framework = mapping["framework"]
        collection_name = mapping["collection"]
        pdf_files = sorted(folder_path.glob("*.pdf"))

        if not pdf_files:
            logger.info("No PDFs in %s", folder_path)
            continue

        logger.info(
            "=== %s: %d PDFs → collection '%s' (framework=%s) ===",
            folder_name, len(pdf_files), collection_name, framework,
        )

        for pdf_path in pdf_files:
            file_start = time.perf_counter()
            filename = pdf_path.name
            logger.info("  Processing: %s", filename)

            try:
                # 1. Extract with Unstructured
                processed = await processor.process_document(str(pdf_path))

                if processed.processing_status == "failed":
                    logger.error("    FAILED: %s", filename)
                    continue

                # 2. Derive standard name from filename
                standard_name = (
                    filename.replace(".pdf", "")
                    .replace("_", " ")
                    .replace("-", " ")
                )

                # 3. Chunk
                extra_meta = {
                    "framework": framework,
                    "standard_name": standard_name,
                    "source_file": filename,
                }
                chunks = chunker.chunk_processed_document(
                    processed,
                    collection_type=collection_name,
                    extra_metadata=extra_meta,
                )

                if not chunks:
                    logger.warning("    No chunks produced for %s", filename)
                    continue

                # 4. Embed in batches
                texts = [c["text"] for c in chunks]
                all_embeddings: list[list[float]] = []
                for i in range(0, len(texts), EMBED_BATCH):
                    batch = texts[i:i + EMBED_BATCH]
                    batch_embs = await embedder.embed_batch(batch)
                    all_embeddings.extend(batch_embs)

                for chunk, emb in zip(chunks, all_embeddings):
                    chunk["embedding"] = emb

                # 5. Store in ChromaDB
                await vector_store.add_documents(collection_name, chunks)

                elapsed = time.perf_counter() - file_start
                total_chunks += len(chunks)
                total_files += 1

                logger.info(
                    "    ✓ %s → %d chunks, %d elements, %d tables (%.1fs)",
                    filename, len(chunks), len(processed.elements),
                    len(processed.tables), elapsed,
                )

            except Exception:
                logger.exception("    EXCEPTION processing %s", filename)

    total_elapsed = time.perf_counter() - t0
    logger.info("=" * 60)
    logger.info(
        "DONE: %d files, %d total chunks indexed in %.1fs",
        total_files, total_chunks, total_elapsed,
    )

    # Print collection stats
    for stat in vector_store.get_all_stats():
        logger.info("  Collection '%s': %d chunks", stat["name"], stat["count"])


if __name__ == "__main__":
    asyncio.run(index_all())
