#!/bin/bash
# 🧹 Убиваем старые процессы autoposter, кроме себя
for pid in $(pgrep -f "python.*autoposter.py"); do
    if [ "$pid" != "$$" ]; then
        kill "$pid" 2>/dev/null
    fi
done
sleep 1
exit 0
