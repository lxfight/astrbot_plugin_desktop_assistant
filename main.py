"""
桌面悬浮球助手 - AstrBot 平台适配器插件 (服务端)

提供桌面感知和主动对话功能的服务端适配器。
"""

import asyncio
import time
import traceback
import uuid
from typing import Optional

from astrbot import logger
from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import Image, Plain
from astrbot.core.platform import (
    AstrBotMessage,
    MessageMember,
    MessageType,
    Platform,
    PlatformMetadata,
)
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.core.platform.register import register_platform_adapter

from .services.desktop_monitor import DesktopMonitorService, DesktopState
from .services.proactive_dialog import (
    ProactiveDialogService,
    ProactiveDialogConfig,
    TriggerEvent,
    TriggerType,
)
from .ws_handler import ClientManager, WebSocketHandler, ClientDesktopState

# 全局 WebSocket 客户端管理器
client_manager = ClientManager()

# ============================================================================
# 插件主类（占位符，平台适配器通过装饰器注册）
# ============================================================================

class Main(star.Star):
    """
    桌面悬浮球助手插件主类
    
    注意：实际功能由 DesktopAssistantAdapter 平台适配器实现，
    此类仅作为 AstrBot 插件系统的入口点。
    """
    
    def __init__(self, context: star.Context) -> None:
        self.context = context
        self.ws_handler = WebSocketHandler(client_manager)
        
        # 注册 WebSocket 路由
        try:
            # 尝试注册 WebSocket 路由
            # 注意：这里假设 context.app 是 FastAPI/Starlette 应用实例
            if hasattr(self.context, "app"):
                self.context.app.add_websocket_route("/ws/client", self.ws_handler.handle_websocket)
                logger.info("桌面助手 WebSocket 服务已启动: /ws/client")
            else:
                logger.warning("无法注册 WebSocket 路由: context.app 不存在")
        except Exception as e:
            logger.error(f"注册 WebSocket 路由失败: {e}")
            
        logger.info("桌面悬浮球助手插件已加载（平台适配器模式）")


# ============================================================================
# 消息事件类
# ============================================================================

class DesktopMessageEvent(AstrMessageEvent):
    """桌面助手消息事件"""
    
    def __init__(
        self,
        message_str: str,
        message_obj: AstrBotMessage,
        platform_meta: PlatformMetadata,
        session_id: str,
        is_proactive: bool = False
    ):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.is_proactive = is_proactive  # 是否为主动对话触发的消息
        
    async def send(self, message: MessageChain):
        """发送消息"""
        # 通过 WebSocket 发送消息到客户端
        try:
            msg_data = {
                "type": "message",
                "content": str(message), # 暂时转换为字符串，后续优化为结构化数据
                "session_id": self.session_id
            }
            # 尝试直接发送给对应的 session
            await client_manager.send_message(self.session_id, msg_data)
        except Exception as e:
            logger.error(f"WebSocket 发送消息失败: {e}")
            
        await super().send(message)


# ============================================================================
# 平台适配器
# ============================================================================

@register_platform_adapter(
    adapter_name="desktop_assistant",
    desc="桌面悬浮球助手 (服务端) - 提供桌面感知和主动对话功能",
    default_config_tmpl={
        "type": "desktop_assistant",
        "enable": True,
        "id": "desktop_assistant",
        # 桌面监控配置
        "enable_desktop_monitor": True,
        "monitor_interval": 60,
        "max_screenshots": 20,
        "screenshot_max_age_hours": 24,
        # 主动对话配置
        "enable_proactive_dialog": True,
        "proactive_min_interval": 300,
        "proactive_max_interval": 900,
        "proactive_probability": 0.3,
        "window_change_enabled": True,
        "window_change_probability": 0.2,
        "scheduled_greetings_enabled": True,
    },
    adapter_display_name="桌面悬浮球助手",
    support_streaming_message=True
)
class DesktopAssistantAdapter(Platform):
    """桌面悬浮球助手平台适配器"""
    
    def __init__(self, platform_config: dict, event_queue: asyncio.Queue):
        super().__init__(platform_config, event_queue)
        
        self._running = False
        
        # 平台元数据
        self.metadata = PlatformMetadata(
            name="desktop_assistant",
            description="桌面悬浮球助手",
            id=platform_config.get("id", "desktop_assistant"),
        )
        
        # 会话 ID
        self.session_id = f"desktop_assistant!user!{uuid.uuid4().hex[:8]}"
        
        # 桌面监控和主动对话服务
        self.desktop_monitor: Optional[DesktopMonitorService] = None
        self.proactive_dialog: Optional[ProactiveDialogService] = None
        
        logger.info("桌面悬浮球助手适配器已初始化")
        
    def meta(self) -> PlatformMetadata:
        """返回平台元数据"""
        return self.metadata
        
    async def send_by_session(
        self,
        session: MessageSesion,
        message_chain: MessageChain,
    ):
        """通过会话发送消息"""
        # 通过 WebSocket 发送消息到客户端
        try:
            msg_data = {
                "type": "message",
                "content": str(message_chain),
                "session_id": session.session_id
            }
            await client_manager.send_message(session.session_id, msg_data)
        except Exception as e:
            logger.error(f"WebSocket 发送消息失败: {e}")
            
        await super().send_by_session(session, message_chain)
                
    def run(self):
        """返回适配器运行协程"""
        return self._run()
        
    async def _run(self):
        """适配器主运行协程"""
        logger.info("桌面悬浮球助手适配器启动中...")
        
        try:
            self._running = True
            self.status = self.status.__class__.RUNNING
            
            # 启动桌面监控和主动对话服务
            await self._start_monitor_services()
            
            # 保持运行，等待客户端连接或其他事件
            while self._running:
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"桌面悬浮球助手运行错误: {e}")
            logger.error(traceback.format_exc())
            # self.record_error(str(e), traceback.format_exc()) # Platform base class might not have this method exposed or named differently in this version context? Original code had it.
            
    async def _start_monitor_services(self):
        """启动桌面监控和主动对话服务"""
        # 桌面监控服务（接收客户端上报的数据）
        if self.config.get("enable_desktop_monitor", True):
            self.desktop_monitor = DesktopMonitorService(
                proactive_min_interval=self.config.get("proactive_min_interval", 300),
                proactive_max_interval=self.config.get("proactive_max_interval", 900),
                on_state_change=self._on_desktop_state_change,
            )
            
            # 设置 WebSocket 客户端管理器的桌面状态回调
            client_manager.on_desktop_state_update = self._on_client_desktop_state
            
            await self.desktop_monitor.start()
            logger.info("桌面监控服务已启动（等待客户端连接）")
            
            # 主动对话服务
            if self.config.get("enable_proactive_dialog", True):
                proactive_config = ProactiveDialogConfig(
                    random_enabled=True,
                    random_probability=self.config.get("proactive_probability", 0.3),
                    random_min_interval=self.config.get("proactive_min_interval", 300),
                    random_max_interval=self.config.get("proactive_max_interval", 900),
                    window_change_enabled=self.config.get("window_change_enabled", True),
                    window_change_probability=self.config.get("window_change_probability", 0.2),
                    scheduled_enabled=self.config.get("scheduled_greetings_enabled", True),
                )
                
                self.proactive_dialog = ProactiveDialogService(
                    desktop_monitor=self.desktop_monitor,
                    config=proactive_config,
                    on_trigger=self._on_proactive_trigger,
                )
                await self.proactive_dialog.start()
                logger.info("主动对话服务已启动")
                
    async def _on_client_desktop_state(self, client_state: ClientDesktopState):
        """处理客户端上报的桌面状态"""
        if self.desktop_monitor:
            await self.desktop_monitor.handle_client_state(client_state)
    
    async def _on_desktop_state_change(self, state: DesktopState):
        """桌面状态变化回调"""
        logger.debug(f"桌面状态更新: session={state.session_id}, window={state.window_title}")
        
    async def _on_proactive_trigger(self, event: TriggerEvent):
        """主动对话触发回调"""
        logger.info(f"主动对话触发: type={event.trigger_type.value}")
        
        try:
            # 构建主动对话消息
            message_parts = []
            message_str = ""
            
            # 根据触发类型构建不同的提示
            if event.trigger_type == TriggerType.SCHEDULED:
                hint = event.context.get("message_hint", "")
                if hint:
                    message_str = hint
                    message_parts.append(Plain(f"[系统提示] {hint}"))
            elif event.trigger_type == TriggerType.WINDOW_CHANGE:
                current_window = event.context.get("current_window", "未知窗口")
                message_str = f"我看到你切换到了 {current_window}，有什么可以帮助你的吗？"
                message_parts.append(Plain(f"[桌面感知] 检测到窗口切换: {current_window}"))
            elif event.trigger_type == TriggerType.RANDOM:
                message_str = "我在这里陪着你呢，有什么需要帮助的吗？"
                message_parts.append(Plain("[主动问候] 随机触发"))
            elif event.trigger_type == TriggerType.IDLE:
                idle_duration = event.context.get("idle_duration", 0)
                message_str = f"你已经休息了 {int(idle_duration / 60)} 分钟了，需要我帮你做点什么吗？"
                message_parts.append(Plain(f"[空闲检测] 空闲 {int(idle_duration / 60)} 分钟"))
            
            # 添加截图（如果有）
            if event.has_screenshot:
                message_parts.append(Image.fromFileSystem(event.desktop_state.screenshot_path))
                if not message_str:
                    message_str = "[桌面截图]"
                    
            if not message_parts:
                return
                
            # 构建 AstrBotMessage
            abm = AstrBotMessage()
            abm.self_id = "desktop_assistant"
            abm.sender = MessageMember("proactive_system", "主动对话系统")
            abm.type = MessageType.FRIEND_MESSAGE
            abm.session_id = self.session_id
            abm.message_id = str(uuid.uuid4())
            abm.timestamp = int(time.time())
            abm.message = message_parts
            abm.message_str = message_str
            abm.raw_message = event
            
            # 创建消息事件并提交（标记为主动对话）
            msg_event = DesktopMessageEvent(
                message_str=message_str,
                message_obj=abm,
                platform_meta=self.metadata,
                session_id=self.session_id,
                is_proactive=True
            )
            
            self.commit_event(msg_event)
            logger.info(f"已提交主动对话事件: {message_str[:50]}...")
            
        except Exception as e:
            logger.error(f"处理主动对话触发失败: {e}")
            logger.error(traceback.format_exc())
            
    async def terminate(self):
        """终止适配器"""
        logger.info("正在停止桌面悬浮球助手...")
        
        self._running = False
        
        # 停止主动对话服务
        if self.proactive_dialog:
            try:
                await self.proactive_dialog.stop()
            except Exception as e:
                logger.error(f"停止主动对话服务失败: {e}")
                
        # 停止桌面监控服务
        if self.desktop_monitor:
            try:
                await self.desktop_monitor.stop()
            except Exception as e:
                logger.error(f"停止桌面监控服务失败: {e}")
        
        self.status = self.status.__class__.STOPPED
        logger.info("桌面悬浮球助手已停止")