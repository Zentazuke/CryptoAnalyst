"""make_release.py — build a CLEAN, shareable zip of the analyst. (P0.2, 2026-07-04)

Why: a hand-zipped folder once shipped a real .env, a Windows .venv, node_modules,
and the DuckDB data files. Packaging by hand is how secrets leak — so this script
makes it mechanical: an explicit WHITELIST of what goes in, a BLOCKLIST that aborts
the build if anything sensitive would be included, and a manifest printed at the end.

    python scripts/make_release.py                 # writes dist/crypto-analyst-<date>.zip
    python scripts/make_release.py --out my.zip
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# What ships. Directories are included recursively (minus EXCLUDE_PATTERNS).
INCLUDE = [
    "analyst",
    "frontend/src",
    "frontend/index.html",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/tsconfig.json",
    "frontend/vite.config.ts",
    "tests",
    "scripts",
    "README.md",
    "MODEL_CARD.md",
    "SIGNAL_CARD.md",
    "STRATEGY_GRAVEYARD.md",
    "VRP_MODEL_CARD.md",
    "pyproject.toml",
    ".env.example",
    ".gitignore",
]

# If a file matching any of these would land in the zip, ABORT — never "warn and ship".
FORBIDDEN = [
    ".env", "*.env", "!.env.example",       # real env files (example is fine)
    "*.duckdb", "*.duckdb.wal",
    "*apiKey*", "*api_key*", "*.pem", "*.key",
]
EXCLUDE_PATTERNS = [
    "__pycache__", ".pytest_cache", ".venv", "node_modules", "dist",
    "*.pyc", ".DS_Store", "data", "*.duckdb", "*.duckdb.wal", "*.log",
]


def excluded(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    for pat in EXCLUDE_PATTERNS:
        if any(fnmatch.fnmatch(p, pat) for p in parts):
            return True
    return False


def forbidden(rel: str) -> bool:
    name = os.path.basename(rel)
    if name == ".env.example":
        return False
    return any(fnmatch.fnmatch(name, pat) for pat in FORBIDDEN if not pat.startswith("!"))


def collect() -> list[Path]:
    files: list[Path] = []
    for item in INCLUDE:
        p = ROOT / item
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not excluded(str(f.relative_to(ROOT))):
                    files.append(f)
        else:
            print(f"  note: {item} not found — skipped")
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a clean release zip (whitelist-based)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    out = Path(args.out) if args.out else ROOT / "dist" / f"crypto-analyst-{time.strftime('%Y%m%d')}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    files = collect()
    bad = [str(f.relative_to(ROOT)) for f in files if forbidden(str(f.relative_to(ROOT)))]
    if bad:
        print("ABORT — these files must NEVER ship (fix the tree or the whitelist):")
        for b in bad:
            print(f"  {b}")
        return 1
    if not files:
        print("ABORT — nothing to package (run from the repo root?)")
        return 1

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.relative_to(ROOT))
    total_mb = out.stat().st_size / 1e6
    print(f"wrote {out} — {len(files)} files, {total_mb:.1f} MB")
    if total_mb > 25:
        print("WARNING: unusually large for a source release — check the manifest:")
        for f in files[:20]:
            print(f"  {f.relative_to(ROOT)}")
    print("\nSanity: no .env, no .venv, no node_modules, no *.duckdb, no data/ — enforced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
