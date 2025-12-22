"""
桌面悬浮球助手 - GUI 模块

包含悬浮球窗口、对话窗口和各种 UI 组件。
"""

from .app import DesktopApp
from .screenshot_selector import ScreenshotSelectorWindow, RegionScreenshotCapture

__all__ = [
    "DesktopApp",
    "ScreenshotSelectorWindow",
    "RegionScreenshotCapture",
]