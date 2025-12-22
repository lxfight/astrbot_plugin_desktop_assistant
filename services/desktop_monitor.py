"""
桌面监控服务

提供定时截图监控、截图存储管理和主动对话触发功能。
"""

import asyncio
import glob
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional

from astrbot import logger

from .screen_capture import ScreenCaptureService


@dataclass
class DesktopState:
    """桌面状态"""
    screenshot_path: str
    capture_time: datetime
    active_window: Optional[str] = None
    window_title: Optional[str] = None
    previous_window: Optional[str] = None
    window_changed: bool = False


@dataclass
class ScreenshotStorageConfig:
    """截图存储配置"""
    max_count: int = 20
    max_age_hours: int = 24
    save_dir: str = "./temp/screenshots"


class ScreenshotManager:
    """截图存储管理器"""
    
    def __init__(self, config: ScreenshotStorageConfig):
        """
        初始化截图管理器
        
        Args:
            config: 截图存储配置
        """
        self.config = config
        self._ensure_dir()
        
    def _ensure_dir(self):
        """确保存储目录存在"""
        os.makedirs(self.config.save_dir, exist_ok=True)
        
    def get_screenshot_files(self) -> List[str]:
        """
        获取所有截图文件，按修改时间排序（最新在前）
        
        Returns:
            截图文件路径列表
        """
        pattern = os.path.join(self.config.save_dir, "screenshot_*.png")
        files = glob.glob(pattern)
        return sorted(files, key=os.path.getmtime, reverse=True)
        
    def cleanup_old_screenshots(self):
        """清理旧截图"""
        files = self.get_screenshot_files()
        current_time = time.time()
        max_age_seconds = self.config.max_age_hours * 3600
        
        removed_count = 0
        
        # 按数量清理
        if len(files) > self.config.max_count:
            for filepath in files[self.config.max_count:]:
                try:
                    os.remove(filepath)
                    removed_count += 1
                except OSError as e:
                    logger.warning(f"删除截图失败: {filepath}, 错误: {e}")
                    
        # 按时间清理
        for filepath in files[:self.config.max_count]:
            try:
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    os.remove(filepath)
                    removed_count += 1
            except OSError as e:
                logger.warning(f"删除截图失败: {filepath}, 错误: {e}")
                
        if removed_count > 0:
            logger.debug(f"已清理 {removed_count} 个旧截图")
            
    def get_storage_stats(self) -> dict:
        """
        获取存储统计信息
        
        Returns:
            包含文件数量、总大小等信息的字典
        """
        files = self.get_screenshot_files()
        total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
        
        return {
            "count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "max_count": self.config.max_count,
            "save_dir": self.config.save_dir
        }


class DesktopMonitorService:
    """桌面监控服务"""
    
    def __init__(
        self,
        screenshot_interval: int = 60,
        proactive_min_interval: int = 300,
        proactive_max_interval: int = 600,
        max_screenshots: int = 20,
        screenshot_max_age_hours: int = 24,
        save_dir: str = "./temp/screenshots",
        on_state_change: Optional[Callable[[DesktopState], Any]] = None,
        on_proactive_trigger: Optional[Callable[[DesktopState], Any]] = None,
        on_window_change: Optional[Callable[[DesktopState], Any]] = None,
    ):
        """
        初始化桌面监控服务
        
        Args:
            screenshot_interval: 截图间隔（秒）
            proactive_min_interval: 主动对话最小间隔（秒）
            proactive_max_interval: 主动对话最大间隔（秒）
            max_screenshots: 最大保留截图数量
            screenshot_max_age_hours: 截图最大保留时间（小时）
            save_dir: 截图保存目录
            on_state_change: 桌面状态变化回调
            on_proactive_trigger: 主动对话触发回调
            on_window_change: 窗口变化回调
        """
        self.screenshot_interval = screenshot_interval
        self.proactive_min_interval = proactive_min_interval
        self.proactive_max_interval = proactive_max_interval
        self.on_state_change = on_state_change
        self.on_proactive_trigger = on_proactive_trigger
        self.on_window_change = on_window_change
        
        # 截图存储管理
        storage_config = ScreenshotStorageConfig(
            max_count=max_screenshots,
            max_age_hours=screenshot_max_age_hours,
            save_dir=save_dir
        )
        self._screenshot_manager = ScreenshotManager(storage_config)
        self._screen_capture = ScreenCaptureService(save_dir=save_dir)
        
        self._is_monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._proactive_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._last_state: Optional[DesktopState] = None
        self._last_window_title: Optional[str] = None
        self._proactive_enabled = True
        
    @property
    def is_monitoring(self) -> bool:
        """是否正在监控"""
        return self._is_monitoring
        
    @property
    def proactive_enabled(self) -> bool:
        """是否启用主动对话"""
        return self._proactive_enabled
        
    @proactive_enabled.setter
    def proactive_enabled(self, value: bool):
        """设置是否启用主动对话"""
        self._proactive_enabled = value
        
    @property
    def screenshot_manager(self) -> ScreenshotManager:
        """获取截图管理器"""
        return self._screenshot_manager
        
    async def start(self):
        """启动监控"""
        if self._is_monitoring:
            return
            
        self._is_monitoring = True
        logger.info("桌面监控服务启动中...")
        
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        if self._proactive_enabled:
            self._proactive_task = asyncio.create_task(self._proactive_loop())
            
        logger.info("桌面监控服务已启动")
            
    async def stop(self):
        """停止监控"""
        self._is_monitoring = False
        logger.info("桌面监控服务停止中...")
        
        tasks = [self._monitor_task, self._proactive_task, self._cleanup_task]
        for task in tasks:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        self._monitor_task = None
        self._proactive_task = None
        self._cleanup_task = None
        
        logger.info("桌面监控服务已停止")
            
    async def _monitor_loop(self):
        """监控循环"""
        while self._is_monitoring:
            try:
                state = await self._capture_state()
                if state:
                    # 检测窗口变化
                    if self._last_window_title != state.window_title:
                        state.previous_window = self._last_window_title
                        state.window_changed = True
                        self._last_window_title = state.window_title
                        
                        # 触发窗口变化回调
                        if self.on_window_change and state.window_changed:
                            await self._safe_callback(self.on_window_change, state)
                            
                    # 触发状态变化回调
                    if self.on_state_change:
                        await self._safe_callback(self.on_state_change, state)
                        
                    self._last_state = state
            except Exception as e:
                logger.error(f"桌面监控错误: {e}")
                
            await asyncio.sleep(self.screenshot_interval)
            
    async def _cleanup_loop(self):
        """定时清理循环"""
        while self._is_monitoring:
            try:
                # 每 10 分钟清理一次
                await asyncio.sleep(600)
                self._screenshot_manager.cleanup_old_screenshots()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"截图清理错误: {e}")
            
    async def _proactive_loop(self):
        """主动对话循环"""
        while self._is_monitoring and self._proactive_enabled:
            try:
                # 随机等待时间
                wait_time = random.randint(
                    self.proactive_min_interval,
                    self.proactive_max_interval
                )
                logger.debug(f"下次主动对话将在 {wait_time} 秒后触发")
                await asyncio.sleep(wait_time)
                
                if not self._is_monitoring or not self._proactive_enabled:
                    break
                    
                # 获取当前状态并触发主动对话
                state = await self._capture_state()
                if state and self.on_proactive_trigger:
                    logger.info(f"触发主动对话，当前窗口: {state.window_title}")
                    await self._safe_callback(self.on_proactive_trigger, state)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"主动对话触发错误: {e}")
                
    async def _capture_state(self) -> Optional[DesktopState]:
        """捕获桌面状态"""
        try:
            screenshot_path = self._screen_capture.capture_full_screen_to_file()
            if not screenshot_path:
                return None
                
            # 获取活动窗口信息（平台特定）
            active_window, window_title = self._get_active_window_info()
            
            return DesktopState(
                screenshot_path=screenshot_path,
                capture_time=datetime.now(),
                active_window=active_window,
                window_title=window_title,
                previous_window=self._last_window_title,
                window_changed=False
            )
        except Exception as e:
            logger.error(f"捕获桌面状态失败: {e}")
            return None
            
    def _get_active_window_info(self) -> tuple:
        """获取活动窗口信息"""
        import sys
        
        try:
            if sys.platform == "win32":
                return self._get_active_window_windows()
            elif sys.platform == "darwin":
                return self._get_active_window_macos()
            else:
                return self._get_active_window_linux()
        except Exception:
            return (None, None)
            
    def _get_active_window_windows(self) -> tuple:
        """获取 Windows 活动窗口信息"""
        try:
            import ctypes
            from ctypes import wintypes
            
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            
            # 获取进程名
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            return (str(pid.value), buffer.value)
        except Exception:
            return (None, None)
            
    def _get_active_window_macos(self) -> tuple:
        """获取 macOS 活动窗口信息"""
        try:
            import subprocess
            script = '''
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                set appName to name of frontApp
                set windowTitle to ""
                try
                    set windowTitle to name of front window of frontApp
                end try
                return appName & "|" & windowTitle
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split("|")
                return (parts[0], parts[1] if len(parts) > 1 else "")
        except Exception:
            pass
        return (None, None)
        
    def _get_active_window_linux(self) -> tuple:
        """获取 Linux 活动窗口信息"""
        try:
            import subprocess
            
            # 获取活动窗口 ID
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return (None, None)
                
            window_id = result.stdout.strip()
            
            # 获取窗口标题
            result = subprocess.run(
                ["xdotool", "getwindowname", window_id],
                capture_output=True,
                text=True
            )
            window_title = result.stdout.strip() if result.returncode == 0 else ""
            
            return (window_id, window_title)
        except Exception:
            return (None, None)
            
    async def _safe_callback(self, callback: Callable, *args):
        """安全调用回调"""
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"回调执行错误: {e}")
            
    def get_last_state(self) -> Optional[DesktopState]:
        """获取最后的桌面状态"""
        return self._last_state
        
    async def trigger_proactive_now(self) -> Optional[DesktopState]:
        """立即触发一次主动对话"""
        logger.info("手动触发主动对话")
        state = await self._capture_state()
        if state and self.on_proactive_trigger:
            await self._safe_callback(self.on_proactive_trigger, state)
        return state
        
    def get_storage_stats(self) -> dict:
        """
        获取截图存储统计信息
        
        Returns:
            存储统计信息字典
        """
        return self._screenshot_manager.get_storage_stats()
        
    def cleanup_screenshots(self):
        """手动清理截图"""
        self._screenshot_manager.cleanup_old_screenshots()