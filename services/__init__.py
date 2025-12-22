"""
服务层模块

提供屏幕捕获、音频录制、桌面监控、主动对话等服务。
"""

from .desktop_monitor import DesktopMonitorService, DesktopState
from .proactive_dialog import (
    ProactiveDialogService,
    ProactiveDialogConfig,
    TriggerEvent,
    TriggerType,
)

__all__ = [
    "DesktopMonitorService",
    "DesktopState",
    "ProactiveDialogService",
    "ProactiveDialogConfig",
    "TriggerEvent",
    "TriggerType",
]