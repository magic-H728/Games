# Gunicorn配置文件

# 绑定地址
bind = "0.0.0.0:8000"

# 工作进程数（建议CPU核心数 * 2 + 1）
workers = 1  # 开发环境用1个，生产环境可以改为 3 或 5

# 工作模式 - 使用uvicorn的worker
worker_class = "uvicorn.workers.UvicornWorker"

# 超时时间
timeout = 120

# 日志
accesslog = "-"  # 输出到stdout
errorlog = "-"   # 输出到stderr
loglevel = "info"

# 预加载应用
preload_app = True
