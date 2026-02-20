#!/usr/bin/env python3
"""Ingest all regulatory PDF documents into ChromaDB.

Walks ``backend/data/compliance_rules/`` and processes every PDF through
the full pipeline: Unstructured extraction → ComplianceChunker → OpenAI
embeddings → ChromaDB storage (``regulatory_frameworks`` collection).

Usage
-----
    # from the project root
    python scripts/ingest_compliance_rules.py

    # custom data directory
    python scripts/ingest_compliance_rules.py --data-dir /path/to/rules

    # dry-run (no actual processing)
    python scripts/ingest_compliance_rules.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

# Ensure the backend package is importable
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_BACKEND_DIR))

# Now we can import app modules
from app.config import get_settings  # noqa: E402
from app.pipelines.ingest_pipeline import IngestPipeline  # noqa: E402
from app.services.document_processor import DocumentProcessor  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402
from app.services.mongo_service import MongoService  # noqa: E402
from app.services.vector_store import VectorStoreService  # noqa: E402
from app.utils.chunking import ComplianceChunker  # noqa: E402

# ---------------------------------------------------------------------------
# Folder → framework mapping
# ---------------------------------------------------------------------------

FRAMEWORK_MAP: dict[str, dict[str, str]] = {
    "IndAS_Standards": {
        "framework": "IndAS",
        "doc_type": "regulation",
        "description": "Indian Accounting Standards (converged IFRS)",
    },
    "Disclosure_Checklists": {
        "framework": "Disclosure",
        "doc_type": "checklist",
        "description": "ICAI / KPMG disclosure requirement checklists",
    },
    "Schedule_III": {
        "framework": "Schedule_III",
        "doc_type": "regulation",
        "description": "Companies Act 2013 — Schedule III",
    },
    "SEBI_LODR": {
        "framework": "SEBI_LODR",
        "doc_type": "regulation",
        "description": "SEBI Listing Obligations and Disclosure Requirements",
    },
    "RBI_Norms": {
        "framework": "RBI",
        "doc_type": "regulation",
        "description": "Reserve Bank of India regulatory norms",
    },
    "ESG_BRSR": {
        "framework": "ESG_BRSR",
        "doc_type": "regulation",
        "description": "Business Responsibility & Sustainability Reporting",
    },
    "Auditing_Standards": {
        "framework": "Auditing",
        "doc_type": "regulation",
        "description": "Auditing Standards (SA / SQC) issued by ICAI",
    },
}


# ---------------------------------------------------------------------------
# Progress helper
# ---------------------------------------------------------------------------

def _progress_bar(current: int, total: int, width: int = 40) -> str:
    """Simple text progress bar (no tqdm dependency required)."""
    filled = int(width * current / max(total, 1))
    bar = "█" * filled + "░" * (width - filled)
    pct = 100 * current / max(total, 1)
    return f"  [{bar}] {pct:5.1f}%  ({current}/{total})"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

async def ingest_all_rules(
    data_dir: str,
    dry_run: bool = False,
) -> dict[str, list[dict]]:
    """Walk *data_dir*, process every PDF, return per-framework summaries."""

    # Settings loads .env relative to cwd — ensure we're in backend/
    original_cwd = os.getcwd()
    os.chdir(str(_BACKEND_DIR))
    # Clear the lru_cache so pydantic-settings picks up the .env in the new cwd
    get_settings.cache_clear()
    settings = get_settings()
    os.chdir(original_cwd)

    rules_path = Path(data_dir)

    if not rules_path.exists():
        print(f"Error: data directory not found — {rules_path}")
        sys.exit(1)

    # Discover PDFs
    plan: list[tuple[Path, dict[str, str]]] = []
    for subdir in sorted(rules_path.iterdir()):
        if not subdir.is_dir():
            continue
        fw_info = FRAMEWORK_MAP.get(subdir.name, {
            "framework": subdir.name,
            "doc_type": "regulation",
            "description": subdir.name,
        })
        pdfs = sorted(subdir.glob("*.pdf"))
        for pdf in pdfs:
            plan.append((pdf, fw_info))

    if not plan:
        print("No PDF files found. Make sure the data directory contains sub-folders with PDFs.")
        print(f"  Expected structure: {rules_path}/<FrameworkName>/*.pdf")
        return {}

    print(f"\n{'='*60}")
    print(f"  NFRA Compliance Rules Ingestion")
    print(f"{'='*60}")
    print(f"  Data directory : {rules_path}")
    print(f"  Total PDFs     : {len(plan)}")
    print(f"  Frameworks     : {len({i['framework'] for _, i in plan})}")
    print(f"  Dry run        : {dry_run}")
    print(f"{'='*60}\n")

    if dry_run:
        for pdf, info in plan:
            print(f"  [DRY] {info['framework']:20s}  {pdf.name}")
        print(f"\n  Would process {len(plan)} files. Exiting (dry-run).")
        return {}

    # Initialise services (once, shared across all files)
    print("Initialising services...")

    try:
        processor = DocumentProcessor(
            api_key=settings.UNSTRUCTURED_API_KEY,
            api_url=settings.UNSTRUCTURED_API_URL,
        )
        embeddings = EmbeddingService(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
        vector_store = VectorStoreService(persist_dir=settings.CHROMA_PERSIST_DIR)

        # We need a Mongo connection for the pipeline
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = mongo_client[settings.MONGODB_DB_NAME]
        mongo_service = MongoService(db)

        pipeline = IngestPipeline(
            document_processor=processor,
            embedding_service=embeddings,
            vector_store=vector_store,
            mongo_service=mongo_service,
            chunker=ComplianceChunker(chunk_size=1000, chunk_overlap=200),
        )

        print("Services ready.\n")

        # Process each PDF
        summaries: dict[str, list[dict]] = {}
        total = len(plan)
        t_start = time.perf_counter()

        for idx, (pdf_path, fw_info) in enumerate(plan, 1):
            framework = fw_info["framework"]
            doc_type = fw_info["doc_type"]
            filename = pdf_path.name

            print(f"\n{'─'*60}")
            print(f"  [{idx}/{total}]  {framework} / {filename}")
            print(f"{'─'*60}")

            # Create a document record in Mongo first
            from datetime import datetime, timezone
            doc_data = {
                "filename": filename,
                "status": "uploaded",
                "file_path": str(pdf_path),
                "metadata": {
                    "source_filename": filename,
                    "file_size_bytes": pdf_path.stat().st_size,
                    "content_type": "application/pdf",
                    "framework_tags": [framework],
                    "upload_timestamp": datetime.now(timezone.utc),
                },
            }
            doc_id = await mongo_service.insert_document("documents", doc_data)

            # Run the pipeline
            result = await pipeline.run(
                file_path=str(pdf_path),
                document_id=doc_id,
                doc_type=doc_type,
                framework_tags=[framework],
                extra_metadata={"framework": framework},
            )

            summaries.setdefault(framework, []).append(result)

            status_icon = "✓" if result["status"] == "processed" else "✗"
            print(
                f"  {status_icon}  chunks={result['chunks_created']:4d}  "
                f"collection={result['collection']}  "
                f"time={result['processing_time']:.1f}s"
            )
            print(_progress_bar(idx, total))

        elapsed = time.perf_counter() - t_start

        # Close Mongo
        mongo_client.close()

    except Exception:
        import traceback
        traceback.print_exc()
        return {}

    # Print summary
    print(f"\n\n{'='*60}")
    print(f"  INGESTION COMPLETE")
    print(f"{'='*60}")
    total_chunks = 0
    for fw, results in sorted(summaries.items()):
        fw_chunks = sum(r["chunks_created"] for r in results)
        success = sum(1 for r in results if r["status"] == "processed")
        failed = len(results) - success
        total_chunks += fw_chunks
        print(
            f"  {fw:25s}  files={len(results):3d}  "
            f"chunks={fw_chunks:5d}  ok={success}  fail={failed}"
        )
    print(f"{'─'*60}")
    print(f"  Total chunks created : {total_chunks}")
    print(f"  Total time           : {elapsed:.1f}s")
    print(f"{'='*60}\n")

    # Show collection stats
    print("ChromaDB collection stats:")
    for stat in vector_store.get_all_stats():
        print(f"  {stat['name']:30s}  count={stat['count']}")

    return summaries


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest regulatory compliance PDFs into ChromaDB"
    )
    parser.add_argument(
        "--data-dir",
        default=str(_BACKEND_DIR / "data" / "compliance_rules"),
        help="Path to compliance_rules directory (default: backend/data/compliance_rules)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be processed without actually processing",
    )
    args = parser.parse_args()
    asyncio.run(ingest_all_rules(args.data_dir, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
