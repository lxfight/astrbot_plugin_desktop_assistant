"""
桌面悬浮球助手 - AstrBot 平台适配器插件 (服务端)

提供桌面感知和主动对话功能的服务端适配器。
支持通过 QQ (NapCat/OneBot11) 远程控制桌面端截图。
"""

import asyncio
import time
import traceback
import uuid
from typing import Optional

from astrbot import logger
from astrbot.api import star, llm_tool
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import Image, Plain
from astrbot.api.star import Context
from astrbot.core.star.register import register_command
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
from .ws_handler import ClientManager, WebSocketHandler, ClientDesktopState, ScreenshotResponse
from .ws_server import WebSocketServer, patch_client_manager_for_websockets

# 全局 WebSocket 客户端管理器
client_manager = ClientManager()

# 为 ClientManager 添加 websockets 库支持
patch_client_manager_for_websockets(client_manager)

# 全局 WebSocket 处理器
ws_handler: Optional[WebSocketHandler] = None

# 全局 WebSocket 服务器
ws_server: Optional[WebSocketServer] = None

# WebSocket 服务器启动锁，防止重复启动
_ws_server_lock = asyncio.Lock()
_ws_server_started = False

# ============================================================================
# 插件主类（占位符，平台适配器通过装饰器注册）
# ============================================================================

class Main(star.Star):
    """
    桌面悬浮球助手插件主类
    
    提供：
    1. 平台适配器模式：桌面监控和主动对话
    2. 命令模式：支持通过 /screenshot 命令远程截图
    3. 独立 WebSocket 服务器：端口 6190
    """
    
    def __init__(self, context: star.Context) -> None:
        global ws_handler, ws_server
        
        self.context = context
        self.ws_handler = WebSocketHandler(client_manager)
        ws_handler = self.ws_handler  # 保存全局引用
        
        # 创建独立的 WebSocket 服务器（端口 6190）
        self.ws_server = WebSocketServer(client_manager, host="0.0.0.0", port=6190)
        ws_server = self.ws_server  # 保存全局引用
        
        logger.info("桌面悬浮球助手插件已加载（平台适配器模式）")
        logger.info("📡 WebSocket 服务器将在端口 6190 启动")
        logger.info("   桌面客户端请连接: ws://服务器IP:6190/ws/client?session_id=xxx&token=xxx")
        
        # 注意：不在 __init__ 中启动 WebSocket 服务器
        # 因为此时可能没有运行中的事件循环
        # 服务器将在首次命令调用时懒启动
    
    async def _ensure_ws_server_started(self):
        """确保 WebSocket 服务器已启动（懒启动模式，带锁保护）"""
        global _ws_server_started, _ws_server_lock
        
        # 快速检查，避免不必要的锁竞争
        if _ws_server_started:
            logger.debug("WebSocket 服务器已在运行中")
            return True
        
        logger.info("📡 检测到 WebSocket 服务器尚未启动，正在初始化...")
        
        async with _ws_server_lock:
            # 双重检查
            if _ws_server_started:
                logger.debug("WebSocket 服务器已由其他协程启动")
                return True
            
            try:
                logger.info("🚀 正在启动 WebSocket 服务器 (端口 6190)...")
                success = await self.ws_server.start()
                _ws_server_started = success
                
                if success:
                    logger.info("=" * 50)
                    logger.info("✅ WebSocket 服务器启动成功！")
                    logger.info(f"   监听地址: ws://0.0.0.0:6190")
                    logger.info(f"   桌面客户端请连接: ws://服务器IP:6190/ws/client?session_id=xxx&token=xxx")
                    logger.info("=" * 50)
                else:
                    logger.error("=" * 50)
                    logger.error("❌ WebSocket 服务器启动失败！")
                    logger.error("   可能原因：")
                    logger.error("   1. 端口 6190 已被占用")
                    logger.error("   2. websockets 库未安装 (pip install websockets)")
                    logger.error("   3. 权限不足")
                    logger.error("=" * 50)
                
                return success
            except Exception as e:
                logger.error(f"启动 WebSocket 服务器时发生异常: {e}")
                logger.error(traceback.format_exc())
                return False
    
    # ========================================================================
    # 命令处理器：远程截图
    # ========================================================================
    
    @register_command("screenshot", alias={"截图", "jietu"})
    async def screenshot_command(self, event: AstrMessageEvent):
        """远程截图：通过 QQ 发送此命令让桌面端执行截图并返回图片"""
        # 使用 print 确保日志一定输出（绕过可能的日志级别问题）
        print("[DesktopAssistant] 📸 收到截图命令，正在处理...")
        logger.info("📸 收到截图命令，正在处理...")
        
        try:
            # 确保 WebSocket 服务器已启动
            print("[DesktopAssistant] 正在确保 WebSocket 服务器启动...")
            ws_started = await self._ensure_ws_server_started()
            print(f"[DesktopAssistant] WebSocket 服务器启动结果: {ws_started}")
            
            if not ws_started:
                logger.error("截图命令失败：WebSocket 服务器未能启动")
                yield event.plain_result(
                    "❌ WebSocket 服务器未能启动，无法执行远程截图。\n\n"
                    "请检查服务器日志获取更多信息。"
                )
                return
            
            client_count = client_manager.get_active_clients_count()
            print(f"[DesktopAssistant] WebSocket 服务器状态: 已启动, 当前连接数: {client_count}")
            logger.info(f"WebSocket 服务器状态: 已启动, 当前连接数: {client_count}")
            
            async for result in self._do_remote_screenshot(event, None, silent=True):
                yield result
        except Exception as e:
            print(f"[DesktopAssistant] 截图命令执行异常: {e}")
            logger.error(f"截图命令执行异常: {e}")
            import traceback
            traceback.print_exc()
            yield event.plain_result(f"❌ 截图命令执行异常: {str(e)}")
    
    @llm_tool("view_desktop_screen")
    async def view_desktop_screen_tool(self, event: AstrMessageEvent):
        """
        查看用户当前电脑桌面屏幕内容。
        
        当你需要了解用户正在做什么、查看用户屏幕上的内容、或者需要根据用户当前的操作提供帮助时，
        可以调用此函数来获取用户桌面的实时截图。
        
        使用场景举例：
        - 用户询问"看看我在干什么"
        - 用户说"帮我看看这个怎么操作"
        - 用户说"屏幕上显示的是什么"
        - 需要根据用户当前操作提供上下文相关的帮助
        
        返回：桌面截图图片
        """
        # 确保 WebSocket 服务器已启动
        await self._ensure_ws_server_started()
        
        async for result in self._do_remote_screenshot(event, None, silent=False):
            yield result
    
    async def _do_remote_screenshot(
        self,
        event: AstrMessageEvent,
        target_session_id: Optional[str] = None,
        silent: bool = False
    ):
        """
        执行远程截图
        
        Args:
            event: 消息事件
            target_session_id: 目标客户端 session_id
            silent: 静默模式，只返回图片不返回额外信息
        """
        # 检查是否有已连接的客户端
        connected_clients = client_manager.get_connected_client_ids()
        
        logger.info(f"📊 当前连接状态: 已连接客户端数量 = {len(connected_clients)}")
        if connected_clients:
            logger.info(f"   客户端列表: {[c[:20] + '...' for c in connected_clients]}")
        else:
            logger.warning("   ⚠️ 没有任何客户端连接！")
        
        if not connected_clients:
            # 提供更详细的诊断信息
            ws_status = "✅ 已启动" if _ws_server_started else "❌ 未启动"
            
            logger.warning("截图请求失败：没有已连接的桌面客户端")
            
            yield event.plain_result(
                f"❌ 没有已连接的桌面客户端，无法执行截图。\n\n"
                f"📊 诊断信息：\n"
                f"• WebSocket 服务器状态: {ws_status}\n"
                f"• 监听端口: 6190\n"
                f"• 已连接客户端: 0\n\n"
                f"📝 排查步骤：\n"
                f"1. 确认桌面客户端程序已启动\n"
                f"2. 检查桌面客户端配置的服务器 IP 地址是否正确（不是 localhost）\n"
                f"3. 确保服务器防火墙已开放 6190 端口\n"
                f"4. 查看桌面客户端控制台是否有连接错误\n\n"
                f"💡 使用 `.桌面状态` 命令可查看更详细的连接信息"
            )
            return
        
        try:
            # 请求截图
            response: ScreenshotResponse = await client_manager.request_screenshot(
                session_id=target_session_id,
                timeout=30.0
            )
            
            if response.success and response.image_path:
                # 截图成功，发送图片
                yield event.image_result(response.image_path)
                # 静默模式下不发送额外信息
                if not silent:
                    yield event.plain_result(
                        f"✅ 截图成功！\n"
                        f"• 分辨率: {response.width}x{response.height}\n"
                        f"• 客户端: {response.session_id[:16]}..."
                    )
            else:
                # 截图失败
                error_msg = response.error_message or "未知错误"
                yield event.plain_result(f"❌ 截图失败: {error_msg}")
                
        except Exception as e:
            logger.error(f"远程截图异常: {e}")
            logger.error(traceback.format_exc())
            yield event.plain_result(f"❌ 截图请求异常: {str(e)}")
    
    @register_command("desktop_status", alias={"桌面状态", "zhuomian"})
    async def desktop_status_command(self, event: AstrMessageEvent):
        """查看当前连接的桌面客户端状态"""
        # 确保 WebSocket 服务器已启动
        ws_started = await self._ensure_ws_server_started()
        
        connected_clients = client_manager.get_connected_client_ids()
        
        # 构建 WebSocket 服务器状态
        ws_status = "✅ 运行中" if ws_started else "❌ 未启动"
        
        if not connected_clients:
            yield event.plain_result(
                f"📊 桌面客户端状态\n\n"
                f"🌐 WebSocket 服务器: {ws_status}\n"
                f"📡 监听端口: 6190\n\n"
                f"❌ 当前没有已连接的客户端。\n\n"
                f"请确保桌面端程序已启动并配置正确的服务器地址。\n"
                f"连接地址: ws://服务器IP:6190/ws/client?session_id=xxx&token=xxx"
            )
            return
        
        # 构建状态信息
        status_lines = ["📊 桌面客户端状态\n"]
        status_lines.append(f"🌐 WebSocket 服务器: {ws_status}")
        status_lines.append(f"📡 监听端口: 6190")
        status_lines.append(f"✅ 已连接客户端数量: {len(connected_clients)}\n")
        
        for i, session_id in enumerate(connected_clients, 1):
            state = client_manager.get_client_state(session_id)
            status_lines.append(f"\n【客户端 {i}】")
            status_lines.append(f"• Session: {session_id[:20]}...")
            
            if state:
                status_lines.append(f"• 活动窗口: {state.active_window_title or '未知'}")
                status_lines.append(f"• 进程: {state.active_window_process or '未知'}")
                if state.received_at:
                    status_lines.append(f"• 最后更新: {state.received_at.strftime('%H:%M:%S')}")
        
        yield event.plain_result("\n".join(status_lines))


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