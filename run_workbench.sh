#!/usr/bin/env bash
set -e
export PYTHONPATH="$(pwd)/src"
uvicorn app.api:app --reload
