#!/bin/bash

set -e

log_file='/var/log/nginx/access.log'

echo "Top 5 ip by requests: "
awk '{print $1}' "$log_file" | sort | uniq -c | sort -nr | head -5