#!/bin/bash
set -e

docker-compose build
docker tag hawall_server aramk0/hawall_server
docker push aramk0/hawall_server
