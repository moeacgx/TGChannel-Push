"""API routes package."""

from techannel_push.api.routes.channels import router as channels_router
from techannel_push.api.routes.creatives import router as creatives_router
from techannel_push.api.routes.groups import router as groups_router
from techannel_push.api.routes.health import router as health_router
from techannel_push.api.routes.settings import router as settings_router
from techannel_push.api.routes.slots import router as slots_router

__all__ = [
    "channels_router",
    "creatives_router",
    "groups_router",
    "health_router",
    "settings_router",
    "slots_router",
]
