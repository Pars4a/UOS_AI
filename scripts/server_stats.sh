#!/bin/bash

set -e

echo "Total CPU Usage: "

top -bn1 | grep %Cpu

echo "*************************************** "


echo "Total memory usage: "

free -h

echo "*************************************** "



echo "Total disk usage: "

df -h

echo "*************************************** "



# top 5 processes in cpu usge: 

ps -eo pid,comm,%cpu --sort=-%cpu | head -6

echo "*************************************** "


# top 5 processes in memory usge: 

ps -eo pid,comm,%mem --sort=-%mem | head -6

