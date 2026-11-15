#!/usr/bin/env bash
# FalconDM - Turbo Download Accelerator (Linux & macOS launcher)
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    exec python3 main.py "$@"
elif command -v python >/dev/null 2>&1; then
    exec python main.py "$@"
else
    echo "Error: Python 3 is required to run FalconDM. Please install python3."
    exit 1
fi

