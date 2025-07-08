#!/bin/bash
set -e

cd "$THE_DIR"

source .env

cd "$H_PATH"

source "$VENV_PATH"

pkill uvicorn

cd "$R_PATH"

git pull

uvicorn "$APPNAME:app" --host "$HOST" --port "$PORT_NUM" --reload > logs/output.log 2>&1 &

