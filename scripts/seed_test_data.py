#!/usr/bin/env python3
"""Seed test data (sample annual reports) for development.

Usage:
    python scripts/seed_test_data.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


async def seed_data() -> None:
    """Seed MongoDB with sample test data."""
    print("Seeding test data...")

    # TODO: Connect to MongoDB
    # TODO: Insert sample document records
    # TODO: Insert sample compliance reports
    # TODO: Insert sample chat sessions

    print("Test data seeded successfully.")


def main() -> None:
    """Entry point for the seeding script."""
    asyncio.run(seed_data())


if __name__ == "__main__":
    main()
