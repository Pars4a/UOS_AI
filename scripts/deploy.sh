#!/bin/bash
set -e

source .env

cd "$0_PATH"

source "$VENV_PATH"

pkill uvicorn

cd "$1_PATH"

git pull

uvicorn "$APPNAME:app" --host "$HOST" --port "$PORT_NUM" --reload > logs/output.log 2>&1 &
