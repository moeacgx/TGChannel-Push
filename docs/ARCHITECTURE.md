# 架构设计

> 目标：用尽量简单、可落地的方式，解决"多频道、多槽位、定时发布/置顶、下次轮换删除旧消息、随机槽位跨频道分配"的核心问题。

## 1. 技术栈

- **语言**：Python 3.10+
- **Bot 框架**：aiogram v3（异步、生态成熟）
- **Bot 运行模式**：Webhook（需要公网域名/反代）
- **Web 框架**：FastAPI（管理面板 + Webhook 端点）
- **前端**：Vue 3 + Element Plus（简洁管理后台）
- **调度**：APScheduler（CronTrigger），用数据库持久化任务
- **存储**：SQLite（MVP），后续可换 PostgreSQL
- **ORM**：SQLAlchemy 2.x（异步）
- **时区**：统一使用北京时间 (UTC+8)
- **部署**：Docker（后续），先支持 Windows 直接跑

为什么不直接用系统 cron？
- 你这里需要“多租户/多分组/可暂停/可立即触发/可恢复状态”，纯 cron 脚本会迅速失控；APScheduler 更容易把“任务=槽位”落到数据层。

## 2. 领域模型（核心对象）

### Channel（频道）
- `tg_chat_id`（频道 chat id）
- `title`
- `status`（active/left）
- `permissions_snapshot`（可选）
- `created_at / updated_at`

### ChannelGroup（频道分组）
- `name`
- `channels[]`

### Slot（槽位=独立任务）
- `group_id`
- `name`（可选，便于识别槽位用途）
- `index`（1..N，槽位序号）
- `type`：fixed / random
- `enabled`：true/false（暂停/继续）
- `publish_cron`：例如 `0 9 * * *`
- `delete_policy`：
  - `mode`: none / cron / after_seconds
  - `delete_cron` 或 `delete_after_seconds`
- `strategy`（随机槽位策略参数，可选）

### AdCreative（广告配置）
- `slot_id`
- `name`（可选，便于识别素材用途）
- `source_chat_id`（管理员私聊 chat id）
- `source_message_id`（源消息 id）
- `render_mode`：copy_message / resend (预留)
- `extra_inline_keyboard`（可选：按钮 JSON）
- `enabled`

### Placement（投放记录：保证能删旧消息）
- `channel_id`
- `slot_id`
- `last_post_message_id`
- `last_posted_creative_id`（便于追踪随机轮换）
- `last_cycle_key`（用于“本轮次”分配一致性）
- `updated_at`

## 3. 关键业务流程

### 3.1 获取“源消息”
管理员在私聊把消息发给 Bot：
1) Bot 记录该消息（chat_id + message_id）作为 `AdCreative.source_*`
2) （可选）在 Bot 的管理菜单里为其配置按钮/投放策略

为什么用“源消息 + copyMessage”？
- `copyMessage` 可以最大程度保留媒体/格式/按钮（或重设按钮），并且不会显示“转发来源”，更适合广告。

### 3.2 发布/置顶（按槽位执行）
每次触发（publish cron）：
1) 根据 `Slot.type` 选出要投放的 `AdCreative`
2) 对该槽位面向的所有频道计算分配（随机槽位要“跨频道尽量不重复”）
3) 对每个频道执行：
   - 若 `Placement.last_post_message_id` 存在：先 `deleteMessage` 删除旧广告
   - `copyMessage` 到频道，得到新 `message_id`
   - `pinChatMessage` 置顶
   - 更新 Placement（记录新 message_id）

### 3.3 删除"已置顶 xxx"系统提醒
`pinChatMessage` 会在频道产生一条系统提示消息（service message），会影响观感。
处理方式：
- Bot 必须是频道管理员且有删除消息权限；
- 在 `pinChatMessage` 后，尝试删除 `message_id + 1`（通常是置顶服务消息）；
- 为安全起见，先用 `copyMessage` 测试该消息是否为服务消息：
  - 如果复制成功，说明是普通消息，不应删除（删除复制产生的消息）
  - 如果复制失败，说明是服务消息，可以安全删除

### 3.4 自动删除（保持频道整洁）
每个槽位都有自己的删除策略：
- `none`：不自动删，等下次 publish 轮换时删旧再发
- `after_seconds`：发布后延迟 N 秒删除
- `cron`：按 cron 执行删除（适合“每天 23:50 清理”之类）

实现上：建议用“删除任务队列（按 placement 维度）”，而不是每条消息单独上一个 cron。

## 4. 随机槽位"跨频道分配"策略

输入：
- 一个随机槽位绑定 K 条 Creative
- 分组内有 M 个频道

目标：
- 每一轮触发时，尽量让不同频道展示不同 creative（K>=M 时做到完全不重复）
- **同一频道不能同时出现两个相同的广告**：如果某 creative 已在该频道展示中，跳过不重复发布

去重规则（核心）：
1. 发布前检查该频道的所有活跃 placement
2. 如果目标 creative 已在该频道的某个槽位展示中，则跳过
3. 选择下一个可用的 creative 继续尝试
4. 如果所有 creative 都已在该频道展示，则该频道本轮跳过

建议算法（简单可复现）：
- 生成 `cycle_key = floor(now / slot_cycle_window)`（例如按触发次数/日期）
- 用 `hash(cycle_key + slot_id)` 作为随机种子，对 creatives 做一次 shuffle
- 按频道列表排序后，做轮转分配：
  ```python
  for channel in channels:
      # 获取该频道当前所有活跃的 creative_id
      active_creative_ids = get_active_creatives_for_channel(channel.id)

      # 尝试分配一个不重复的 creative
      for i in range(len(shuffled_creatives)):
          candidate = shuffled_creatives[(channel_index + offset + i) % K]
          if candidate.id not in active_creative_ids:
              # 找到可用的，执行发布
              publish(channel, candidate)
              break
      else:
          # 所有 creative 都已在展示，跳过
          log.info(f"Channel {channel.id} skipped: all creatives already active")
  ```
- 把 `offset` 持久化到 Slot，以保证下次轮换"继续往后走"，覆盖更均匀

## 5. 编辑 vs 删除重发（你提到的“媒体冲突”）

工程上建议：**MVP 一律删除重发**（最稳、规则最少）。

想做“智能编辑”也可以，但要按 Bot API 限制制定规则：
- 文本→文本：`editMessageText`
- 图文（caption）→图文：`editMessageCaption`
- 媒体更换：`editMessageMedia`（但从“有媒体”变“无媒体”/类型变化有坑）

折中方案：
- 若旧/新都“无媒体”：允许 edit
- 若旧/新都“有媒体且同类型”：允许 edit
- 其他情况：delete + copy

## 6. Web 管理面板

### 为什么需要 Web 面板

虽然 Bot 内联菜单也能实现管理功能，但考虑到：
- 分组/槽位/频道/素材的批量操作更直观
- 状态一览和日志查看更方便
- 后续扩展（审核、统计）更容易

**MVP 直接提供 Web 管理面板**，Bot 端只处理：
- 接收管理员私聊的广告素材消息
- Webhook 接收频道更新（用于清理置顶提示）
- 频道入群/退群事件

### Web 面板功能模块

1. **仪表盘**
   - 已管理频道数、分组数、槽位数、活跃任务数
   - 最近发布/删除日志

2. **频道管理**
   - 查看所有已加入的频道
   - 频道状态（active/left）
   - 频道权限检查

3. **分组管理**
   - 创建/编辑/删除分组
   - 批量添加/移除频道
   - 设置分组默认槽位数量（可配置 N）

4. **槽位管理**
   - 创建/编辑/删除槽位
   - 设置槽位类型（固定/随机）
   - 设置发布 cron 表达式
   - 设置删除策略
   - 暂停/继续/立即执行
   - 清除置顶

5. **素材管理**
   - 查看所有素材
   - 为素材配置按钮
   - 绑定到槽位
   - 启用/禁用

6. **日志查看**
   - 发布记录
   - 删除记录
   - 错误日志

### 技术实现

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Browser                              │
│                   (Vue 3 + Element Plus)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Server                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Web API    │  │  Webhook    │  │  Static Files       │  │
│  │  /api/*     │  │  /webhook   │  │  (Vue build)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                              │                                │
│  ┌───────────────────────────┴───────────────────────────┐  │
│  │                   aiogram Bot                          │  │
│  │         (Webhook mode, 处理 TG 更新)                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                              │                                │
│  ┌───────────────────────────┴───────────────────────────┐  │
│  │                  APScheduler                           │  │
│  │         (Cron 任务调度，发布/删除)                      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLite Database                            │
└─────────────────────────────────────────────────────────────┘
```

## 7. 预留扩展（商业化 v2）

> 当前 MVP 暂不实现，但数据模型已预留扩展字段。

如果后期要做"用户自助购买广告位"，可扩展：

- `Account`：系统登录用户（或 TG 用户）
- `Tenant`：一个客户的工作空间（一个租户管理多个分组/频道/槽位/广告）
- `Membership`：账号与租户关系（owner/admin/operator）
- `Plan`/`Quota`：套餐与配额（可创建分组数、槽位数、频道数、随机槽位 creative 数等）
- `Order`：订单（待支付/已支付/已关闭）
- `Payment`：支付回调记录（易支付回调入库，防重放）
- `ReviewTask`：审核待办（例如“新广告素材审核”“新分组开通”）

建议的权限边界（KISS 版）：
- MVP：只做**单管理员模式**（只允许你自己操作）
- v2：引入租户与权限、再对接易支付、再上审核流

## 8. 安全与权限

- **管理员白名单**：只有配置在 `ADMIN_TG_IDS` 中的 TG 用户 ID 才能操作
- **Web 面板认证**：简单 token 认证（后续可升级为 JWT）
- **Bot Token、密钥**：只放环境变量（`.env`），不要写进仓库
