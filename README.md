# TeChannel-Push

Telegram 多频道广告置顶机器人 - 支持槽位管理、定时发布、自动删除

## 功能特性

- 🔄 **槽位管理**：固定槽位 + 随机槽位，每个槽位独立调度
- 📺 **频道分组**：批量管理多个频道，按分组设置广告任务
- ⏰ **定时发布**：基于 Cron 表达式的灵活发布时间配置（北京时间）
- 🗑️ **自动删除**：支持延迟删除、定时删除、下次轮换删除
- 🎯 **智能去重**：同一频道不会同时展示相同广告
- 🌐 **Web 面板**：直观的管理界面，支持所有配置操作
- 📊 **日志追踪**：完整的操作日志，便于排查问题

## 核心概念

- **频道（Channel）**：Bot 被邀请并具备必要权限后，自动纳入管理
- **频道分组（Channel Group）**：把频道按业务分组，任务面向分组配置
- **槽位（Slot）**：一个分组拥有 N 个槽位（可配置），每个槽位是独立任务单元
  - **固定槽位**：只绑定 1 条广告配置
  - **随机槽位**：绑定多条广告配置，用于轮换，同频道不重复
- **广告素材（Ad Creative）**：源消息 + 可选按钮 + 发布/删除策略
- **投放记录（Placement）**：记录每次发布的 message_id，用于下次轮换删除

## 技术栈

- **后端**：Python 3.10+ / FastAPI / aiogram v3 / SQLAlchemy / APScheduler
- **前端**：Vue 3 / Element Plus
- **数据库**：SQLite（可扩展至 PostgreSQL）
- **Bot 模式**：Webhook
- **时区**：北京时间 (UTC+8)

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 安装 Python 依赖
pip install -e .

# 安装前端依赖
cd web && npm install && cd ..
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

配置项说明：
- `BOT_TOKEN`：Telegram Bot Token（可选，也可在 Web 面板配置）
- `WEBHOOK_URL`：Webhook 地址（如 `https://yourdomain.com/webhook`）
- `ADMIN_TG_IDS`：管理员 Telegram ID 列表，逗号分隔
- `DATABASE_URL`：数据库连接地址（默认 SQLite）

### 3. 使用 PM2 启动（推荐）

PM2 是 Node.js 的进程管理器，可以让服务在后台稳定运行。

#### 安装 PM2

```bash
npm install -g pm2
```

#### 启动服务

```bash
# 创建日志目录
mkdir logs

# 启动所有服务（后端 + 前端）
pm2 start ecosystem.config.cjs

# 查看运行状态
pm2 status

# 查看实时日志
pm2 logs

# 只查看后端日志
pm2 logs techannel-backend

# 只查看前端日志
pm2 logs techannel-frontend
```

#### PM2 常用命令

```bash
pm2 status              # 查看所有进程状态
pm2 logs                # 查看所有日志
pm2 logs <name>         # 查看指定服务日志
pm2 restart all         # 重启所有服务
pm2 restart <name>      # 重启指定服务
pm2 stop all            # 停止所有服务
pm2 delete all          # 删除所有进程
pm2 monit               # 打开监控面板
```

#### 设置开机自启（可选）

```bash
# 生成启动脚本
pm2 startup

# 保存当前进程列表
pm2 save
```

### 4. Web 面板登录

- 后端 API: http://localhost:8000
- 前端面板: http://localhost:3000
- API 文档: http://localhost:8000/docs

**默认登录密码**: `admin123`

首次登录后请在「系统设置」页面修改密码。

### 5. 直接启动（开发模式）

如果不想用 PM2，也可以手动启动：

```bash
# 启动后端
python -m techannel_push

# 另开终端启动前端
cd web && npm run dev
```

## Docker 部署（推荐）

**零配置启动**：克隆项目后直接运行，无需任何配置文件！

```bash
# 克隆项目
git clone https://github.com/yourname/TeChannel-push.git
cd TeChannel-push

# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

启动后访问 http://localhost:8000，使用默认密码 `admin123` 登录。

在「系统设置」页面配置：
- Bot Token（从 @BotFather 获取）
- 管理员 ID（可选）
- 修改登录密码（建议）

### Docker 常用命令

```bash
docker-compose up -d        # 后台启动
docker-compose down         # 停止服务
docker-compose logs -f      # 查看日志
docker-compose restart      # 重启服务
docker-compose pull && docker-compose up -d  # 更新镜像
```

### 生产环境配置

如需使用 Webhook 模式，修改 `docker-compose.yml`：

```yaml
environment:
  - TZ=Asia/Shanghai
  - USE_POLLING=false
  - WEBHOOK_URL=https://yourdomain.com/webhook
  - LOG_LEVEL=WARNING
```

### 数据持久化

数据自动保存在项目目录下：
- `./data/` - 数据库文件
- `./logs/` - 日志文件

## 项目结构

```
src/techannel_push/
├── main.py              # 应用入口
├── config.py            # 配置管理
├── database/            # 数据库相关
│   ├── models.py        # SQLAlchemy 模型
│   └── session.py       # 数据库会话
├── bot/                 # Telegram Bot
│   ├── bot.py           # Bot 初始化
│   └── handlers/        # 消息处理器
├── api/                 # Web API
│   ├── routes/          # 路由定义
│   └── deps.py          # 依赖注入
├── scheduler/           # 调度器
│   ├── scheduler.py     # APScheduler 配置
│   └── jobs/            # 定时任务
└── services/            # 业务逻辑
    ├── channel.py       # 频道服务
    ├── slot.py          # 槽位服务
    ├── creative.py      # 素材服务
    └── publisher.py     # 发布服务

web/                     # Vue 3 前端
├── src/
│   ├── views/           # 页面组件
│   ├── api/             # API 调用
│   └── router/          # 路由配置
└── ...
```

## 使用流程

1. **添加 Bot 到频道**：将 Bot 添加为频道管理员（需要发消息、删消息、置顶权限）
2. **创建分组**：在 Web 面板创建频道分组，将频道加入分组
3. **创建槽位**：为分组创建广告槽位，设置发布时间和删除策略
4. **上传素材**：私聊 Bot 发送广告消息，保存为素材
5. **绑定素材**：将素材绑定到槽位
6. **启动任务**：启用槽位，等待定时发布

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 代码检查
ruff check src/

# 运行测试
pytest
```

## 文档

- [架构设计](docs/ARCHITECTURE.md)
- [数据模型](docs/DATA_MODEL.md)
- [开发路线](docs/ROADMAP.md)

## License

MIT
