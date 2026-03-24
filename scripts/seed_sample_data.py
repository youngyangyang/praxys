#!/usr/bin/env python3
"""Seed the data/ directory with sample data for quick start.

Copies data/sample/ → data/ so new users can run the app immediately
without real API credentials. Safe to run multiple times (overwrites).
"""
import os
import shutil


def seed() -> None:
    base = os.path.join(os.path.dirname(__file__), "..")
    sample_dir = os.path.join(base, "data", "sample")
    data_dir = os.path.join(base, "data")

    if not os.path.exists(sample_dir):
        print("No sample data found. Run scripts/generate_sample_data.py first.")
        return

    for source in ["garmin", "stryd", "oura"]:
        src = os.path.join(sample_dir, source)
        dst = os.path.join(data_dir, source)
        if not os.path.exists(src):
            continue
        os.makedirs(dst, exist_ok=True)
        for fname in os.listdir(src):
            shutil.copy2(os.path.join(src, fname), os.path.join(dst, fname))
            print(f"  {source}/{fname} → data/{source}/{fname}")

    print("\nSample data seeded. You can now run:")
    print("  python -m uvicorn api.main:app --reload")
    print("  cd web && npm run dev")


if __name__ == "__main__":
    seed()
