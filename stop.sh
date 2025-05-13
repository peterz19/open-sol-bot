#!/bin/bash

#!/bin/bash

# 定义要停止的进程名称数组
processes=(
    "cache_preloader/main.py"
    "wallet_tracker/main.py"
    "trading/main.py"
    "tg_bot/main.py"
)

# 遍历进程名称
for process in "${processes[@]}"; do
    # 查找进程 PID
    pid=$(ps aux | grep "[p]ython.*$process" | awk '{print $2}')

    if [ ! -z "$pid" ]; then
        echo "正在停止进程: $process (PID: $pid)"
        kill $pid

        # 等待进程结束
        for i in {1..5}; do
            if ! ps -p $pid > /dev/null; then
                echo "进程已停止: $process"
                break
            fi
            sleep 1
        done

        # 如果进程仍然存在，强制终止
        if ps -p $pid > /dev/null; then
            echo "强制终止进程: $process (PID: $pid)"
            kill -9 $pid
        fi
    else
        echo "未找到进程: $process"
    fi
done

echo "所有进程已停止"
