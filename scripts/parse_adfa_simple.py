#!/usr/bin/env python3
"""
Minimal ADFA parser for the numeric-space-separated trace files.

Output CSV: adfa_parsed.csv
Columns: filepath, split, is_anomaly, timestamp, host, message
"""

import argparse
import csv
from pathlib import Path
from datetime import datetime

def read_text_file(p: Path):
    """Read file with fallback encodings."""
    for enc in ("utf-8", "latin-1"):
        try:
            return p.read_text(encoding=enc, errors="replace")
        except Exception:
            continue
    return p.read_bytes().decode("utf-8", errors="replace")

def collapse_whitespace(s: str) -> str:
    """Collapse multiple spaces/newlines into single spaces."""
    return " ".join(s.split())

def infer_split_and_label(rel_path: Path):
    """Infer TRAINING/VALIDATE/ATTACK/OTHER and label (0=normal,1=attack)."""
    parts = [p.lower() for p in rel_path.parts]
    is_attack = any("attack" in p for p in parts)
    if any("training" in p for p in parts):
        split = "TRAINING"
    elif any("validate" in p or "validation" in p for p in parts):
        split = "VALIDATE"
    elif is_attack:
        split = "ATTACK"
    else:
        split = "OTHER"
    return split, (1 if is_attack else 0)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", required=True, help="Path to ADFA raw folder")
    parser.add_argument("--output", "-o", required=True, help="CSV output path")
    args = parser.parse_args()

    root = Path(args.input).expanduser().resolve()
    out = Path(args.output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(root.rglob("*.txt"))

    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["filepath", "split", "is_anomaly", "timestamp", "host", "message"])
        writer.writeheader()

        for p in txt_files:
            try:
                raw = read_text_file(p)
            except Exception as e:
                print(f"WARNING: could not read {p}: {e}")
                continue

            message = collapse_whitespace(raw)
            ts = datetime.utcfromtimestamp(p.stat().st_mtime).isoformat() + "Z"
            rel = p.relative_to(root)
            split, is_anomaly = infer_split_and_label(rel)

            writer.writerow({
                "filepath": str(rel),
                "split": split,
                "is_anomaly": is_anomaly,
                "timestamp": ts,
                "host": "ADFA",
                "message": message
            })

    print(f" Done — wrote {out}")

if __name__ == "__main__":
    main()

