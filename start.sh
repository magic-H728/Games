#!/bin/bash

# 躲猫猫大挑战 启动脚本

case "$1" in
    "dev")
        echo "🔧 开发模式启动..."
        python3 run.py
        ;;
    "prod")
        echo "🚀 生产模式启动 (gunicorn)..."
        gunicorn app.main:app -c gunicorn_conf.py
        ;;
    "stop")
        echo "⏹️ 停止服务..."
        pkill -f "gunicorn app.main:app" 2>/dev/null
        pkill -f "uvicorn app.main:app" 2>/dev/null
        echo "✓ 已停止"
        ;;
    *)
        echo "用法: ./start.sh [dev|prod|stop]"
        echo ""
        echo "  dev   - 开发模式（uvicorn，自动重载）"
        echo "  prod  - 生产模式（gunicorn）"
        echo "  stop  - 停止服务"
        ;;
esac
