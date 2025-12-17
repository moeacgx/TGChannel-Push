"""Handler for receiving ad creatives from admin private messages."""

import json
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration

from tgchannel_push.config import get_effective_admin_ids, get_settings
from tgchannel_push.database import async_session_maker
from tgchannel_push.database.models import AdCreative

logger = logging.getLogger(__name__)
settings = get_settings()

router = Router(name="creative_receiver")


def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in get_effective_admin_ids()


def extract_html_text(text: str | None, entities: list | None) -> str:
    """Extract HTML formatted text from message text and entities."""
    if not text:
        return ""
    if not entities:
        return text
    try:
        return html_decoration.unparse(text, entities)
    except Exception:
        return text


@router.message(Command("start"), F.chat.type == "private")
async def on_start(message: Message) -> None:
    """Handle /start command."""
    if not message.from_user:
        return

    if is_admin(message.from_user.id):
        await message.answer(
            "🤖 <b>TGChannel-Push Bot</b>\n\n"
            "欢迎使用多频道广告置顶机器人喵～\n\n"
            "<b>使用方法：</b>\n"
            "1️⃣ 将 Bot 添加到频道并设为管理员\n"
            "2️⃣ 直接发送广告消息给我保存为素材\n"
            "3️⃣ 在 Web 面板管理分组、槽位和素材\n\n"
            f"<b>Web 面板：</b> http://{settings.api_host}:{settings.api_port}/docs\n"
            f"<b>API Token：</b> 请查看 .env 配置"
        )
    else:
        await message.answer("⚠️ You are not authorized to use this bot.")


@router.message(Command("help"), F.chat.type == "private")
async def on_help(message: Message) -> None:
    """Handle /help command."""
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("⚠️ You are not authorized to use this bot.")
        return

    await message.answer(
        "📖 <b>帮助</b>\n\n"
        "<b>命令：</b>\n"
        "/start - 开始使用\n"
        "/help - 显示帮助\n"
        "/status - 查看系统状态\n\n"
        "<b>保存素材：</b>\n"
        "直接发送文字、图片、视频等消息，Bot 会自动保存为广告素材。\n\n"
        "<b>支持的消息类型：</b>\n"
        "• 文字消息\n"
        "• 图片（带/不带文字）\n"
        "• 视频（带/不带文字）\n"
        "• 文件\n"
        "• GIF 动图"
    )


@router.message(Command("status"), F.chat.type == "private")
async def on_status(message: Message) -> None:
    """Handle /status command."""
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("⚠️ You are not authorized to use this bot.")
        return

    from sqlalchemy import func, select

    from tgchannel_push.database.models import Channel, ChannelGroup, Slot

    async with async_session_maker() as session:
        # Count statistics
        channels_count = await session.scalar(
            select(func.count()).select_from(Channel).where(Channel.status == "active")
        )
        groups_count = await session.scalar(select(func.count()).select_from(ChannelGroup))
        slots_count = await session.scalar(select(func.count()).select_from(Slot))
        enabled_slots = await session.scalar(
            select(func.count()).select_from(Slot).where(Slot.enabled == True)  # noqa: E712
        )
        creatives_count = await session.scalar(select(func.count()).select_from(AdCreative))

    await message.answer(
        "📊 <b>系统状态</b>\n\n"
        f"📺 活跃频道：{channels_count or 0}\n"
        f"📁 分组数：{groups_count or 0}\n"
        f"🎰 槽位数：{slots_count or 0}（启用：{enabled_slots or 0}）\n"
        f"🎨 素材数：{creatives_count or 0}\n\n"
        f"⏰ 时区：{settings.timezone}\n"
        f"🔄 模式：{'Polling' if settings.use_polling else 'Webhook'}"
    )


@router.message(F.chat.type == "private")
async def on_private_message(message: Message) -> None:
    """Handle private messages from admins to save as creatives."""
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("⚠️ You are not authorized to use this bot.")
        return

    # Skip if it's a command (shouldn't reach here due to command handlers, but just in case)
    if message.text and message.text.startswith("/"):
        await message.answer("❓ 未知命令，使用 /help 查看帮助")
        return

    # Determine message type and extract info
    has_media = False
    media_type = None
    media_file_id = None
    caption = None
    caption_preview = None

    if message.photo:
        has_media = True
        media_type = "photo"
        media_file_id = message.photo[-1].file_id  # Get highest resolution
        caption = extract_html_text(message.caption, message.caption_entities)
        caption_preview = (message.caption or "")[:100]  # Preview uses plain text
    elif message.video:
        has_media = True
        media_type = "video"
        media_file_id = message.video.file_id
        caption = extract_html_text(message.caption, message.caption_entities)
        caption_preview = (message.caption or "")[:100]
    elif message.document:
        has_media = True
        media_type = "document"
        media_file_id = message.document.file_id
        caption = extract_html_text(message.caption, message.caption_entities)
        caption_preview = (message.caption or "")[:100]
    elif message.animation:
        has_media = True
        media_type = "animation"
        media_file_id = message.animation.file_id
        caption = extract_html_text(message.caption, message.caption_entities)
        caption_preview = (message.caption or "")[:100]
    elif message.text:
        caption = extract_html_text(message.text, message.entities)
        caption_preview = message.text[:100]
    else:
        await message.answer("⚠️ 不支持的消息类型")
        return

    # Extract inline keyboard if present
    inline_keyboard_json = None
    if message.reply_markup:
        try:
            # Serialize inline keyboard
            keyboard_data = []
            for row in message.reply_markup.inline_keyboard:
                row_data = []
                for button in row:
                    btn = {"text": button.text}
                    if button.url:
                        btn["url"] = button.url
                    elif button.callback_data:
                        btn["callback_data"] = button.callback_data
                    row_data.append(btn)
                keyboard_data.append(row_data)
            inline_keyboard_json = json.dumps(keyboard_data, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to serialize inline keyboard: {e}")

    # Save to database
    async with async_session_maker() as session:
        creative = AdCreative(
            source_chat_id=message.chat.id,
            source_message_id=message.message_id,
            has_media=has_media,
            media_type=media_type,
            media_file_id=media_file_id,
            caption=caption,
            caption_preview=caption_preview,
            inline_keyboard_json=inline_keyboard_json,
        )
        session.add(creative)
        await session.commit()

        media_emoji = {
            "photo": "🖼",
            "video": "🎬",
            "document": "📄",
            "animation": "🎞",
        }.get(media_type, "📝")

        await message.answer(
            f"✅ <b>素材已保存</b>\n\n"
            f"🆔 ID：<code>{creative.id}</code>\n"
            f"{media_emoji} 类型：{media_type or 'text'}\n"
            f"📄 预览：{caption_preview or '(空)'}\n\n"
            f"💡 请在 Web 面板将此素材绑定到槽位"
        )
        logger.info(f"Creative {creative.id} saved from admin {message.from_user.id}")
