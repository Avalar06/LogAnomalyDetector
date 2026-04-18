import re
import csv

input_file = "../logs/live_system.log"
output_file = "../data/parsed_live_logs.csv"

pattern = r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.\d+\+\d{2}:\d{2} (?P<host>\S+) (?P<service>\S+)\[(?P<pid>\d+)\]: (?P<message>.+)"

with open(input_file, "r") as infile, open(output_file, "w", newline="") as outfile:
    writer = csv.writer(outfile)
    writer.writerow(["timestamp", "host", "service", "pid", "message"])

    for line in infile:
        match = re.match(pattern, line)
        if match:
            writer.writerow(match.groups())

print(" Parsed live logs saved to:", output_file)
