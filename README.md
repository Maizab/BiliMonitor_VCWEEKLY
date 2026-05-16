# BiliMonitor_VCWEEKLY

实时监控 Bilibili 视频的播放量、弹幕、评论、收藏、硬币、分享、点赞等数据，带有中V周刊得点计算功能，通过图表可视化展示数据趋势。

## 功能

- **实时数据采集** — 定时拉取 Bilibili API，记录播放量、弹幕、评论、收藏、硬币、分享、点赞、正在观看人数
- **得点计算** — 基于[中V周刊得点算法](https://github.com/YUNSHIYANG/Points_Calculator_for_VCWEEKLY)计算播放、互动、收藏、硬币、点赞五项得分及最终总分
- **可视化图表** — uPlot 渲染多条指标曲线，支持平滑、降采样、同步光标、自定义显示项
- **多视频管理** — 添加/删除/暂停监控、按视频切换图表、可独立开关得点计算
- **实时推送** — SSE (Server-Sent Events) 推送最新数据和日志，无需轮询
- **简单认证** — 基于 SHA256 challenge-response 的密码保护，支持限流和 IP 封禁
- **响应式布局** — 适配桌面和移动端

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3, Flask, SQLite |
| 前端 | Vue 3 (Composition API), Vite, uPlot |
| 实时通信 | Server-Sent Events (SSE) |
| 认证 | SHA256 challenge-response |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. 配置文件

首次运行会自动生成 `config.toml`，也可手动创建：

```toml
# 存储配置
[storage]
db_path = "monitor.db"

# 认证配置（为空则不启用密码）
[auth]
password = ""

# 采集间隔（秒），最小 30
[monitor]
interval = 30

# 限流与封禁
[rate_limit]
challenge_rate = 10
challenge_window = 60
verify_max_failures = 5
verify_failure_window = 300
ban_duration = 300
```

### 3. 启动

```bash
# 后端（默认 http://0.0.0.0:5000）
python web_app.py

# 前端开发模式（默认 http://localhost:5173，自动代理 /api 到后端）
cd frontend && npm run dev
```

### 4. 生产部署

前端构建时使用 `.env.production` 配置，默认部署在 `/video_monitor/` 子路径下，API 请求路径为 `/video_monitor/api`：

```bash
cd frontend && npm run build   # 输出到 frontend/dist/
```

将 `dist/` 目录内容复制到 Web 服务器的 `/video_monitor/` 路径下，然后配置 Nginx 代理 API：

```nginx
# 反向代理 API 到 Flask 后端
location /video_monitor/api {
    proxy_pass http://127.0.0.1:5000/;
    proxy_set_header X-Forwarded-For $remote_addr;
}
```

### 5. 使用

1. 打开前端页面，点击右上角「设置」
2. 输入 B站视频 BV 号添加监控
3. 选择视频即可查看实时数据卡片和历史趋势图

## 项目结构

```
视频数据监控/
├── web_app.py              # 后端主程序（API + 采集 + SSE）
├── config.toml             # 配置文件（自动生成）
├── requirements.txt        # Python 依赖
├── monitor.db              # SQLite 数据文件（自动生成）
├── logs/                   # 日志目录
└── frontend/
    ├── src/
    │   ├── App.vue         # 根组件
    │   ├── components/
    │   │   ├── ChartPanel.vue    # 图表面板（uPlot）
    │   │   ├── DataCards.vue     # 实时数据卡片
    │   │   ├── VideoManager.vue  # 视频列表
    │   │   ├── SettingsModal.vue # 设置弹窗
    │   │   ├── StatusBar.vue     # 顶部状态栏
    │   │   ├── LogBar.vue        # 日志面板
    │   │   ├── ConfirmDialog.vue # 确认对话框
    │   │   └── Toast.vue         # 消息提示
    │   └── composables/
    │       ├── useAPI.js   # API 请求封装
    │       └── useSSE.js   # SSE 实时推送
    ├── vite.config.js
    └── package.json
```

## API 端点

| 方法 | 路径 | 说明 | 需要认证 |
|------|------|------|----------|
| GET | `/auth/check` | 检查是否启用密码 | 否 |
| GET | `/auth/challenge` | 获取认证 challenge | 否 |
| POST | `/auth/verify` | 验证密码 | 否 |
| GET/POST | `/config` | 读取/修改配置 | POST 需要 |
| GET/POST | `/videos` | 列出/添加视频 | POST 需要 |
| PATCH/DELETE | `/videos/<id>` | 更新/删除视频 | 是 |
| GET | `/snapshots` | 获取历史数据 `?video_id=&hours=` | 否 |
| GET | `/latest` | 获取最新快照 `?video_id=` | 否 |
| GET | `/status` | 获取采集状态 | 否 |
| GET | `/log` | 获取最近日志 | 否 |
| GET | `/stream` | SSE 实时推送 | 否 |

## 关于

本项目代码大量使用 AI Agent（Claude Code + DeepSeek）辅助编写，包括架构设计、前后端代码实现、调试与优化。

中V周刊得点算法参考自 [YUNSHIYANG/Points_Calculator_for_VCWEEKLY](https://github.com/YUNSHIYANG/Points_Calculator_for_VCWEEKLY)。

## License

MIT
