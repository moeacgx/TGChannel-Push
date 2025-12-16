# 数据模型

> MVP 阶段的核心表结构，支持：可配置槽位数量、随机槽位去重、北京时区。

## 1. MVP 核心表

### `channels` - 频道表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `tg_chat_id` | BIGINT UNIQUE | Telegram 频道 chat_id |
| `title` | TEXT | 频道标题 |
| `username` | TEXT | 频道用户名（可选） |
| `status` | TEXT | 状态：active / left |
| `permissions_ok` | BOOLEAN | Bot 权限是否充足 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |

### `channel_groups` - 分组表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `name` | TEXT | 分组名称 |
| `default_slot_count` | INTEGER | 默认槽位数量（可配置 N）|
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |

### `channel_group_members` - 分组成员关联表
| 字段 | 类型 | 说明 |
|------|------|------|
| `group_id` | INTEGER FK | 分组 ID |
| `channel_id` | INTEGER FK | 频道 ID |
| UNIQUE(`group_id`, `channel_id`) |

### `slots` - 槽位表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `group_id` | INTEGER FK | 所属分组 |
| `name` | TEXT | 槽位名称（可选，便于识别用途）|
| `slot_index` | INTEGER | 槽位序号（1..N）|
| `slot_type` | TEXT | 类型：fixed / random |
| `enabled` | BOOLEAN | 是否启用 |
| `publish_cron` | TEXT | 发布 cron 表达式（北京时间）|
| `delete_mode` | TEXT | 删除模式：none / cron / after_seconds |
| `delete_cron` | TEXT | 删除 cron（可选）|
| `delete_after_seconds` | INTEGER | 延迟删除秒数（可选）|
| `rotation_offset` | INTEGER | 轮转偏移量（随机槽位用）|
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |
| UNIQUE(`group_id`, `slot_index`) |

### `ad_creatives` - 广告素材表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `slot_id` | INTEGER FK | 绑定槽位（可选，未绑定时为素材库）|
| `name` | TEXT | 素材名称（可选，便于识别用途）|
| `enabled` | BOOLEAN | 是否启用 |
| `source_chat_id` | BIGINT | 源消息所在 chat_id |
| `source_message_id` | INTEGER | 源消息 message_id |
| `has_media` | BOOLEAN | 是否包含媒体 |
| `media_type` | TEXT | 媒体类型（photo/video/document 等）|
| `caption_preview` | TEXT | 文案预览（前 100 字符）|
| `inline_keyboard_json` | TEXT | 自定义按钮 JSON |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |

### `placements` - 投放记录表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `channel_id` | INTEGER FK | 频道 ID |
| `slot_id` | INTEGER FK | 槽位 ID |
| `creative_id` | INTEGER FK | 当前展示的素材 ID |
| `message_id` | INTEGER | 频道中的消息 ID |
| `is_pinned` | BOOLEAN | 是否已置顶 |
| `published_at` | DATETIME | 发布时间 |
| `scheduled_delete_at` | DATETIME | 计划删除时间（可选）|
| `deleted_at` | DATETIME | 实际删除时间（可选）|
| `updated_at` | DATETIME | 更新时间 |
| UNIQUE(`channel_id`, `slot_id`) |

### `operation_logs` - 操作日志表
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `op_type` | TEXT | 操作类型：publish / delete / pin / unpin / error |
| `channel_id` | INTEGER FK | 频道 ID |
| `slot_id` | INTEGER FK | 槽位 ID |
| `creative_id` | INTEGER FK | 素材 ID |
| `message_id` | INTEGER | 消息 ID |
| `status` | TEXT | 状态：success / failed |
| `error_message` | TEXT | 错误信息（可选）|
| `created_at` | DATETIME | 操作时间 |

### `system_config` - 系统配置表
| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | TEXT PK | 配置键 |
| `value` | TEXT | 配置值 |
| `updated_at` | DATETIME | 更新时间 |

## 2. 关键索引

```sql
-- 快速查询频道当前活跃的所有素材（用于去重）
CREATE INDEX idx_placements_channel_active
ON placements(channel_id, deleted_at)
WHERE deleted_at IS NULL;

-- 快速查询待删除的投放记录
CREATE INDEX idx_placements_scheduled_delete
ON placements(scheduled_delete_at)
WHERE scheduled_delete_at IS NOT NULL AND deleted_at IS NULL;

-- 快速查询某槽位的所有素材
CREATE INDEX idx_creatives_slot ON ad_creatives(slot_id);
```

## 3. 去重逻辑说明

### 同一频道不能同时出现相同广告

查询 SQL：
```sql
-- 获取某频道当前所有活跃的 creative_id
SELECT creative_id FROM placements
WHERE channel_id = ? AND deleted_at IS NULL;
```

发布前检查：
```python
async def can_publish_creative(channel_id: int, creative_id: int) -> bool:
    """检查该 creative 是否可以在该频道发布（未被其他槽位占用）"""
    active_creative_ids = await get_active_creative_ids(channel_id)
    return creative_id not in active_creative_ids
```

## 4. v2 预留表（商业化时添加）

> 当前 MVP 不实现，仅作为扩展参考。

- `accounts` - 用户账户
- `tenants` - 租户/工作空间
- `memberships` - 账户-租户关联
- `plans` - 套餐
- `orders` - 订单
- `payments` - 支付记录
- `review_tasks` - 审核任务

