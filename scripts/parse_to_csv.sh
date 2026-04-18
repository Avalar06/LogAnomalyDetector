#!/bin/bash

INPUT_LOG="../logs/sample.log"
OUTPUT_CSV="../data/parsed_logs.csv"

# Header
echo "timestamp,level,ip" > "$OUTPUT_CSV"

# Read and parse
while IFS= read -r line; do
    timestamp=$(echo "$line" | cut -d']' -f1 | tr -d '[')
    level=$(echo "$line" | cut -d']' -f2 | cut -d':' -f1 | tr -d ' ')
    ip=$(echo "$line" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}')
    echo "$timestamp,$level,${ip:-N/A}" >> "$OUTPUT_CSV"
done < "$INPUT_LOG"

echo "✅ CSV saved to $OUTPUT_CSV"
