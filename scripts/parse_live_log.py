import re
import csv
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "logs" / "live_system.log"
OUTPUT_FILE = PROJECT_ROOT / "data" / "parsed_live_logs.csv"

SYSLOG_PATTERN = re.compile(
    r"(?P<month>\w{3})\s+"
    r"(?P<day>\d{1,2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<service>[^\[\]:]+)"
    r"(?:\[(?P<pid>\d+)\])?:\s+"
    r"(?P<message>.+)"
)

MONTH_MAP = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

# ---------------------------------------------------------
# Initialize CSV
# ---------------------------------------------------------

if not OUTPUT_FILE.exists():

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        writer.writerow([
            "timestamp",
            "host",
            "service",
            "pid",
            "message"
        ])

print(f"[PARSER] Monitoring: {INPUT_FILE}")

processed_lines = 0

# ---------------------------------------------------------
# Polling Loop (NO FILE LOCK)
# ---------------------------------------------------------

while True:

    try:

        with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as infile:

            lines = infile.readlines()

        new_lines = lines[processed_lines:]

        for line in new_lines:

            line = line.strip()

            match = SYSLOG_PATTERN.match(line)

            if not match:
                continue

            data = match.groupdict()

            try:

                now = datetime.utcnow()

                month = MONTH_MAP[data["month"]]

                parsed_dt = datetime(
                    year=now.year,
                    month=month,
                    day=int(data["day"]),
                    hour=int(data["time"].split(":")[0]),
                    minute=int(data["time"].split(":")[1]),
                    second=int(data["time"].split(":")[2]),
                    )
                if parsed_dt > now:
                    parsed_dt = parsed_dt.replace(year=now.year - 1)
                timestamp = parsed_dt.strftime("%Y-%m-%dT%H:%M:%S")

            except Exception:

                timestamp = datetime.utcnow().strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )

            row = [
                timestamp,
                data["host"],
                data["service"],
                data["pid"] if data["pid"] else "-1",
                data["message"]
            ]

            with open(
                OUTPUT_FILE,
                "a",
                newline="",
                encoding="utf-8"
            ) as outfile:

                writer = csv.writer(outfile)

                writer.writerow(row)

            print(
                f"[PARSED] "
                f"{data['service']} | "
                f"{data['message'][:80]}"
            )

        processed_lines = len(lines)

        time.sleep(1)

    except KeyboardInterrupt:

        print("\n[PARSER] Stopped.")
        break

    except Exception as e:

        print(f"[PARSER ERROR] {e}")

        time.sleep(2)