# BiliMonitor_VCWEEKLY

实时监控 Bilibili 视频的播放量、弹幕、评论、收藏、硬币、分享、点赞等数据，带有中V周刊得点计算功能，通过图表可视化展示数据趋势。

## 功能

- **实时数据采集** — 定时拉取 Bilibili API，记录播放量、弹幕、评论、收藏、硬币、分享、点赞、正在观看人数
- **灵活调度** — 支持四种采集规则：定长间隔、条件精确、每天定点、每周定点，可按规则组灵活组合
- **规则组管理** — 多组规则独立配置，视频可绑定到不同规则组，满足不同视频的差异化采集需求
- **上传者浏览** — 按 UP 主分组展示视频列表，支持搜索（UP 主名/视频标题/BV 号），显示封面、合作标识
- **得点计算** — 基于[中V周刊得点算法](https://github.com/YUNSHIYANG/Points_Calculator_for_VCWEEKLY)计算播放、互动、收藏、硬币、点赞五项得分及总分；支持以周六凌晨 3 点数据为参考点的增量得分
- **可视化图表** — uPlot 渲染多条指标曲线，支持平滑、LTTB 降采样、同步光标 tooltip、自定义显示项和日期范围
- **多视频管理** — 添加/删除/暂停/恢复监控、按视频切换图表、可独立开关得点计算
- **数据导出** — Excel 导出历史快照数据，支持自定义时间范围和客户端时区
- **实时推送** — SSE (Server-Sent Events) 推送最新快照、日志和状态变更
- **简单认证** — 基于 SHA256 challenge-response 的密码保护，支持限流和 IP 封禁
- **响应式布局** — 适配桌面和移动端

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3, Flask, SQLite |
| 前端 | Vue 3 (Composition API), Vite, uPlot |
| 实时通信 | Server-Sent Events (SSE) |
| 认证 | SHA256 challenge-response |
| 导出 | openpyxl |

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

# 得点计算配置
[score]
# 增量得点参考点（周六凌晨 3 点）查询容差窗口（分钟）
increment_window = 10

# 限流与封禁
[rate_limit]
challenge_rate = 10
challenge_window = 60
verify_max_failures = 5
verify_failure_window = 300
ban_duration = 300
export_rate = 5
export_window = 60

# Bilibili API
[bilibili]
# API 请求最大重试次数（含首次），网络错误和 HTTP 5xx/429 均会重试
max_retries = 3
```

### 3. 启动

```bash
# 后端（默认 http://0.0.0.0:5000）
python app.py

# 前端开发模式（默认 http://localhost:5173，自动代理 /api 到后端）
cd frontend && npm run dev
```

### 4. 生产部署示例

前端构建时使用 `.env.production` 配置 API 路径：

```bash
cd frontend && npm run build   # 输出到 frontend/dist/
```

将 `dist/` 目录部署到 Web 服务器，配置 Nginx 反向代理：

```nginx
location /api {
    proxy_pass http://127.0.0.1:5000/;
    proxy_set_header X-Forwarded-For $remote_addr;
}
```

### 5. 使用

1. 打开页面，点击右上角「管理」
2. 输入密码（如已配置），进入管理面板
3. 「采集设置」标签页 → 输入 BV 号添加视频监控
4. 「规则组管理」标签页 → 创建规则组、配置采集规则
5. 返回主界面，点击 UP 主展开视频列表，选择视频查看图表
6. 点击视频条目上的导出按钮可导出历史数据为 Excel

## 项目结构

```
视频数据监控/
├── app.py                   # Flask 应用入口
├── routes.py                # API 路由（认证、视频管理、规则组、上传者、数据查询、导出、SSE）
├── monitor.py               # 后台采集循环、日志与 SSE 广播
├── database.py              # SQLite 数据库（表结构、CRUD、得点计算）
├── rules.py                 # 规则引擎（定长/条件/每天/每周调度计算）
├── bilibili.py              # B站 API 请求封装（含可配置重试机制）
├── config.py                # TOML 配置加载、校验与持久化
├── ratelimit.py             # 认证和导出限流与封禁
├── utils.py                 # 时间工具函数与得点算法
├── config.toml              # 配置文件（自动生成）
├── requirements.txt         # Python 依赖
├── monitor.db               # SQLite 数据文件（自动生成）
├── logs/                    # 日志目录
├── migrations/              # 数据库迁移脚本
└── frontend/
    ├── src/
    │   ├── App.vue                 # 根组件
    │   ├── main.js                 # 入口
    │   ├── router.js               # 前端路由（hash 模式）
    │   ├── components/
    │   │   ├── ChartPanel.vue      # 图表面板（uPlot）
    │   │   ├── DataCards.vue       # 实时数据卡片与增量得分
    │   │   ├── UploaderBrowser.vue # 上传者浏览与搜索
    │   │   ├── ManagementModal.vue # 视频管理 & 规则组管理面板
    │   │   ├── RuleEditModal.vue   # 规则编辑弹窗
    │   │   ├── SettingsModal.vue   # 设置弹窗（主题/数字格式）
    │   │   ├── ExportModal.vue     # 数据导出弹窗
    │   │   ├── DateTimePicker.vue  # 日期时间选择器
    │   │   ├── TimePicker.vue      # 时间选择器
    │   │   ├── Dropdown.vue        # 下拉选择组件
    │   │   ├── StatusBar.vue       # 顶部状态栏
    │   │   ├── ConfirmDialog.vue   # 确认对话框
    │   │   └── Toast.vue           # 消息提示
    │   ├── composables/
    │   │   ├── useAPI.js           # API 请求封装
    │   │   ├── useSSE.js           # SSE 实时推送
    │   │   ├── useSearch.js        # 前端搜索（UP主/视频/BV号）
    │   │   └── useNumberFormat.js  # 数值格式化
    │   └── utils/
    │       └── imageUrl.js         # B站 CDN 图片 URL 构建
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
| GET/POST | `/rule_groups` | 列出/创建规则组 | POST 需要 |
| GET/PUT/DELETE | `/rule_groups/<id>` | 查看/重命名/删除规则组 | 写操作需要 |
| POST | `/rule_groups/<id>/rules` | 添加规则 | 是 |
| PUT/DELETE | `/rules/<id>` | 编辑/删除规则 | 是 |
| GET | `/uploaders` | 按上传者分组的视频列表 | 否 |
| GET/POST | `/videos` | 列出/添加视频 | POST 需要 |
| PATCH/DELETE | `/videos/<id>` | 更新/删除视频 | 是 |
| GET | `/snapshots` | 获取历史数据 `?video_id=&hours=&start=&end=` | 否 |
| GET | `/latest` | 获取最新快照 `?video_id=` | 否 |
| GET | `/reference` | 获取增量得点参考快照 `?video_id=` | 否 |
| GET | `/status` | 获取采集状态 | 否 |
| GET | `/log` | 获取最近日志 | 否 |
| GET | `/export` | 导出 Excel 数据 `?video_id=&start=&end=&tz=` | 否 |
| GET | `/stream` | SSE 实时推送 | 否 |

## 关于

本项目代码大量使用 AI Agent（Claude Code + DeepSeek）辅助编写，包括架构设计、前后端代码实现、调试与优化。

中V周刊得点算法参考自 [YUNSHIYANG/Points_Calculator_for_VCWEEKLY](https://github.com/YUNSHIYANG/Points_Calculator_for_VCWEEKLY)。

## License

MIT
