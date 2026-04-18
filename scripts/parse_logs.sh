#!/bin/bash

LOGFILE="../logs/sample.log"

echo "Parsed Log Output:"
echo "-------------------"

while IFS= read -r line; do
    timestamp=$(echo "$line" | cut -d']' -f1 | tr -d '[')
    level=$(echo "$line" | cut -d']' -f2 | cut -d':' -f1 | tr -d ' ')
    ip=$(echo "$line" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}')

    echo "Time: $timestamp | Level: $level | IP: ${ip:-N/A}"
done < "$LOGFILE"
