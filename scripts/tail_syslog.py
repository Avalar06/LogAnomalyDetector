import time
import os

source_log = "/var/log/syslog"
target_log = "../logs/live_system.log"

with open(source_log, "r") as src:
    # Move to the end of the file
    src.seek(0, os.SEEK_END)

    while True:
        line = src.readline()
        if not line:
            time.sleep(1)
            continue

        with open(target_log, "a") as out:
            out.write(line)
            print("Captured:", line.strip())
