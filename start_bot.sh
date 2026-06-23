#!/bin/bash
# Sales Trainer Bot 啟動腳本

cd "$(dirname "$0")"

PYTHON="/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python"

exec "$PYTHON" bot_listener.py
