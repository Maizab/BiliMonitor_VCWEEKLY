import threading

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from database import init_db
from monitor import monitor_loop
from routes import register_routes

# ============ Flask 应用 ============
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=0, x_host=0, x_port=0, x_prefix=0)

# 注册所有路由
register_routes(app)


def main():
    """启动服务"""
    init_db()
    threading.Thread(target=monitor_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
