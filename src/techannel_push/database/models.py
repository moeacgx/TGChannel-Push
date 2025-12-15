"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Channel(Base):
    """Telegram channel managed by the bot."""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="active")  # active / left
    permissions_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    group_memberships: Mapped[list["ChannelGroupMember"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    placements: Mapped[list["Placement"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


class ChannelGroup(Base):
    """Group of channels for batch operations."""

    __tablename__ = "channel_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    default_slot_count: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    members: Mapped[list["ChannelGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    slots: Mapped[list["Slot"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class ChannelGroupMember(Base):
    """Association table for channels in groups."""

    __tablename__ = "channel_group_members"

    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channel_groups.id", ondelete="CASCADE"), primary_key=True
    )
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )

    # Relationships
    group: Mapped["ChannelGroup"] = relationship(back_populates="members")
    channel: Mapped["Channel"] = relationship(back_populates="group_memberships")


class Slot(Base):
    """Ad slot - independent scheduling unit."""

    __tablename__ = "slots"
    __table_args__ = (Index("idx_slots_group_index", "group_id", "slot_index", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channel_groups.id", ondelete="CASCADE"), nullable=False
    )
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..N
    slot_type: Mapped[str] = mapped_column(Text, default="fixed")  # fixed / random
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    publish_cron: Mapped[str] = mapped_column(Text, nullable=False)  # Cron expression (Beijing time)
    delete_mode: Mapped[str] = mapped_column(Text, default="none")  # none / cron / after_seconds
    delete_cron: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delete_after_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rotation_offset: Mapped[int] = mapped_column(Integer, default=0)  # For random slot rotation
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    group: Mapped["ChannelGroup"] = relationship(back_populates="slots")
    creatives: Mapped[list["AdCreative"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )
    placements: Mapped[list["Placement"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )


class AdCreative(Base):
    """Ad creative - source message with optional buttons."""

    __tablename__ = "ad_creatives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("slots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    source_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)
    media_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # photo/video/document
    media_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Telegram file_id for media
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Full caption/text content
    caption_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # First 100 chars
    inline_keyboard_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    slot: Mapped[Optional["Slot"]] = relationship(back_populates="creatives")
    placements: Mapped[list["Placement"]] = relationship(back_populates="creative")


class Placement(Base):
    """Placement record - tracks published messages for deletion."""

    __tablename__ = "placements"
    __table_args__ = (
        Index("idx_placements_channel_slot", "channel_id", "slot_id", unique=True),
        Index(
            "idx_placements_channel_active",
            "channel_id",
            "deleted_at",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_placements_scheduled_delete",
            "scheduled_delete_at",
            postgresql_where="scheduled_delete_at IS NOT NULL AND deleted_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("slots.id", ondelete="CASCADE"), nullable=False
    )
    creative_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ad_creatives.id", ondelete="SET NULL"), nullable=True
    )
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scheduled_delete_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    channel: Mapped["Channel"] = relationship(back_populates="placements")
    slot: Mapped["Slot"] = relationship(back_populates="placements")
    creative: Mapped[Optional["AdCreative"]] = relationship(back_populates="placements")


class OperationLog(Base):
    """Operation log for tracking all actions."""

    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    op_type: Mapped[str] = mapped_column(Text, nullable=False)  # publish/delete/pin/unpin/error
    channel_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    creative_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="success")  # success / failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SystemConfig(Base):
    """System configuration key-value store."""

    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
