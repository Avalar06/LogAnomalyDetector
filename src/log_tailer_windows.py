# log_tailer_windows.py

from pathlib import Path
import time
from typing import List
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]

LOGS_DIR = PROJECT_ROOT / "logs"
SOURCE_LOG = LOGS_DIR / "sample.log"
TARGET_LOG = LOGS_DIR / "live_system.log"
OFFSET_FILE = LOGS_DIR / ".sample_simulator.offset"

SLEEP_SECONDS = 1.0
CLEAR_TARGET_AT_START = False


def read_all_lines(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing source log: {path}")

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = [l.rstrip("\n") for l in f.readlines() if l.strip()]

    if not lines:
        raise ValueError("Source log is empty.")
    return lines


def append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8", errors="ignore") as f:
        f.write(line + "\n")


def load_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text().strip())
        except Exception:
            return 0
    return 0


def save_offset(idx: int) -> None:
    OFFSET_FILE.write_text(str(idx))


def rewrite_timestamp(line: str) -> str:
    now = datetime.now()
    fresh_ts = now.strftime("%b %d %H:%M:%S")

    parts = line.split(" ", 3)
    if len(parts) >= 4:
        return f"{fresh_ts} {parts[3]}"
    return f"{fresh_ts} {line}"


def main():
    print("=" * 70)
    print("WINDOWS LOG SIMULATOR – LIVE TIMESTAMP MODE")
    print("=" * 70)

    lines = read_all_lines(SOURCE_LOG)
    total = len(lines)
    last_idx = load_offset()

    if CLEAR_TARGET_AT_START:
        if TARGET_LOG.exists():
            TARGET_LOG.unlink()
        if OFFSET_FILE.exists():
            OFFSET_FILE.unlink()
        last_idx = 0
        print("[RESET] live_system.log and offset cleared.")

    if last_idx >= total:
        print("[DONE] No more demo lines.")
        return

    print(f"[START] Simulating from line {last_idx + 1}")

    for idx in range(last_idx, total):
        raw = lines[idx]
        line = rewrite_timestamp(raw)

        append_line(TARGET_LOG, line)
        save_offset(idx + 1)

        print(f"[{idx + 1}/{total}] {line}")
        time.sleep(SLEEP_SECONDS)

    print("[DONE] Simulation complete.")


if __name__ == "__main__":
    main()
