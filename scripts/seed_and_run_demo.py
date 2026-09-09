"""Seed and run demo — ingests all 6 starter PDFs and prints a summary.

This script is the ONLY place where sample_data/ paths are referenced.
The backend code itself is fully generic.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db.session import async_session_factory
from app.ingestion.pipeline import ingest_document

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed_demo")

SAMPLE_DATA_DIR = Path(__file__).parent.parent / "sample_data"

SAMPLE_PDFS = [
    SAMPLE_DATA_DIR / "india-macroeconomy" / "03-imf-india-2025-article-iv-excerpt.pdf",
    SAMPLE_DATA_DIR / "india-macroeconomy" / "01-india-economic-survey-2024-25-excerpt.pdf",
    SAMPLE_DATA_DIR / "delhivery" / "02-delhivery-annual-report-fy24-excerpt.pdf",
]


async def main():
    logger.info("=" * 60)
    logger.info("FactMesh Demo Seed — Ingesting all 6 starter PDFs")
    logger.info("=" * 60)

    for pdf_path in SAMPLE_PDFS:
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            continue

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Ingesting: {pdf_path.name}")
        logger.info(f"{'=' * 60}")

        async with async_session_factory() as session:
            try:
                doc_id = await ingest_document(session, str(pdf_path))
                logger.info(f"Success! Document ID: {doc_id}")
            except ValueError as e:
                logger.warning(f"Skipped (already ingested): {e}")
            except Exception as e:
                logger.error(f"Failed: {e}")

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    import asyncpg

    conn = await asyncpg.connect(
        user="factmesh",
        password="factmesh",
        database="factmesh",
        host="localhost",
        port=5432,
    )

    doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents")
    fact_count = await conn.fetchval("SELECT COUNT(*) FROM facts")
    rel_count = await conn.fetchval("SELECT COUNT(*) FROM relationships")
    issue_count = await conn.fetchval("SELECT COUNT(*) FROM extraction_issues")

    logger.info(f"Documents:     {doc_count}")
    logger.info(f"Facts:         {fact_count}")
    logger.info(f"Relationships: {rel_count}")
    logger.info(f"Issues:        {issue_count}")

    # Relationship breakdown
    rel_types = await conn.fetch(
        "SELECT relationship_type, COUNT(*) as cnt FROM relationships GROUP BY relationship_type ORDER BY cnt DESC"
    )
    logger.info("\nRelationship breakdown:")
    for row in rel_types:
        logger.info(f"  {row['relationship_type']}: {row['cnt']}")

    # Top entities
    top_entities = await conn.fetch(
        "SELECT entity, COUNT(*) as cnt FROM facts WHERE entity IS NOT NULL GROUP BY entity ORDER BY cnt DESC LIMIT 10"
    )
    logger.info("\nTop entities:")
    for row in top_entities:
        logger.info(f"  {row['entity']}: {row['cnt']} facts")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
