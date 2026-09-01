import sys
import uvicorn

if __name__ == "__main__":
    if "--gunicorn" in sys.argv:
        # 使用gunicorn启动
        import subprocess
        subprocess.run([
            "gunicorn",
            "app.main:app",
            "-c", "gunicorn_conf.py"
        ])
    else:
        # 使用uvicorn启动（开发模式）
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
