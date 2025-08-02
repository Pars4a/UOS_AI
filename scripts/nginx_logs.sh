#!/bin/bash

set -e

log_file="/var/log/nginx/access.log"

if [ ! -f "$log_file" ]; then
    echo "log file not found"
    exit 1
fi

echo "Top 5 ip addresses with most requests"
awk '{print $1}' "$log_file" | sort | uniq -c | sort -nr | head -5

echo -e "\nTop 5 most requested paths"

awk '{print $7}' "$log_file" | sort | uniq -c | sort -nr | head -5

echo -e "\n Top 5 response status codes: "

awk '{print $9}' "$log_file" | sort | uniq -c | sort -nr | head -5

echo -e "Top 5 user agents: "

awk -F\" '{print $6}' "$log_file" | sort | uniq -c | sort -nr | head -5