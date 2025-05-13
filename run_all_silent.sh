#!/bin/bash

nohup uv run ./app/cache-preloader/cache_preloader/main.py > /dev/null 2>&1 &
nohup uv run ./app/wallet-tracker/wallet_tracker/main.py > /dev/null 2>&1 &
nohup uv run ./app/trading/trading/main.py > /dev/null 2>&1 &
nohup uv run ./app/tg-bot/tg_bot/main.py > /dev/null 2>&1 &

