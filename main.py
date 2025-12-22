"""
桌面悬浮球助手 - AstrBot 平台适配器插件

提供可拖拽的悬浮球界面、多模态对话窗口、桌面感知和主动对话功能。
"""

import asyncio
import os
import queue
import threading
import time
import traceback
import uuid
from typing import Any, Optional

from astrbot import logger
from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import File, Image, Plain, Record
from astrbot.core.message.message_event_result import MessageEventResult
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
        logger.info("桌面悬浮球助手插件已加载（平台适配器模式）")


# ============================================================================
# 消息数据类
# ============================================================================

class InputMessage:
    """输入消息（GUI -> Adapter）"""
    
    def __init__(
        self,
        msg_type: str,
        content: Any,
        session_id: str,
        metadata: Optional[dict] = None
    ):
        self.type = msg_type  # text, image, voice, file, screenshot, clipboard
        self.content = content
        self.session_id = session_id
        self.timestamp = time.time()
        self.metadata = metadata or {}


class OutputMessage:
    """输出消息（Adapter -> GUI）"""
    
    def __init__(
        self,
        msg_type: str,
        content: Any,
        session_id: str,
        streaming: bool = False,
        is_complete: bool = False,
        metadata: Optional[dict] = None
    ):
        self.type = msg_type  # text, image, voice, file, thinking, error, end
        self.content = content
        self.session_id = session_id
        self.streaming = streaming
        self.is_complete = is_complete
        self.metadata = metadata or {}


# ============================================================================
# 消息桥接器
# ============================================================================

class MessageBridge:
    """跨线程消息桥接器"""
    
    def __init__(self):
        # 线程安全队列（Qt 线程使用）
        self._input_queue: queue.Queue = queue.Queue()
        self._output_queue: queue.Queue = queue.Queue()
        
        # asyncio 队列（适配器协程使用）
        self.async_input_queue: Optional[asyncio.Queue] = None
        self.async_output_queue: Optional[asyncio.Queue] = None
        
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    def setup_async_queues(self, loop: asyncio.AbstractEventLoop):
        """在 asyncio 事件循环中设置异步队列"""
        self._loop = loop
        self.async_input_queue = asyncio.Queue()
        self.async_output_queue = asyncio.Queue()
        self._running = True
        
    async def start_bridge(self):
        """启动桥接协程"""
        await asyncio.gather(
            self._bridge_input(),
            self._bridge_output()
        )
        
    async def _bridge_input(self):
        """将线程安全队列的输入转发到 asyncio 队列"""
        while self._running:
            try:
                msg = self._input_queue.get_nowait()
                await self.async_input_queue.put(msg)
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"桥接输入错误: {e}")
                await asyncio.sleep(0.1)
                
    async def _bridge_output(self):
        """将 asyncio 队列的输出转发到线程安全队列"""
        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.async_output_queue.get(),
                    timeout=0.1
                )
                self._output_queue.put(msg)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"桥接输出错误: {e}")
                await asyncio.sleep(0.1)
                
    def stop(self):
        """停止桥接"""
        self._running = False
        
    # Qt 线程调用的方法
    def put_input(self, msg: InputMessage):
        """从 Qt 线程放入输入消息"""
        self._input_queue.put(msg)
        
    def get_output(self) -> Optional[OutputMessage]:
        """从 Qt 线程获取输出消息（非阻塞）"""
        try:
            return self._output_queue.get_nowait()
        except queue.Empty:
            return None
            
    # Asyncio 协程调用的方法
    async def get_input(self) -> InputMessage:
        """从适配器协程获取输入消息"""
        return await self.async_input_queue.get()
        
    async def put_output(self, msg: OutputMessage):
        """从适配器协程放入输出消息"""
        await self.async_output_queue.put(msg)


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
        bridge: MessageBridge,
        is_proactive: bool = False
    ):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self._bridge = bridge
        self.is_proactive = is_proactive  # 是否为主动对话触发的消息
        
    async def send(self, message: MessageChain):
        """发送消息到 GUI"""
        await self._send_to_gui(message)
        await super().send(message)
        
    async def send_streaming(self, generator, use_fallback: bool = False):
        """流式发送消息"""
        final_text = ""
        
        async for chain in generator:
            await self._send_to_gui(chain, streaming=True)
            text = chain.get_plain_text() if hasattr(chain, 'get_plain_text') else ""
            final_text += text
            
        # 发送完成标记
        await self._bridge.put_output(OutputMessage(
            msg_type="end",
            content=final_text,
            session_id=self.session_id,
            streaming=True,
            is_complete=True
        ))
        
        await super().send_streaming(generator, use_fallback)
        
    async def _send_to_gui(self, message: MessageChain, streaming: bool = False):
        """将消息放入输出队列"""
        if not message or not message.chain:
            return
            
        for comp in message.chain:
            if isinstance(comp, Plain):
                await self._bridge.put_output(OutputMessage(
                    msg_type="text",
                    content=comp.text,
                    session_id=self.session_id,
                    streaming=streaming
                ))
            elif isinstance(comp, Image):
                try:
                    file_path = await comp.convert_to_file_path()
                    await self._bridge.put_output(OutputMessage(
                        msg_type="image",
                        content=file_path,
                        session_id=self.session_id,
                        streaming=streaming
                    ))
                except Exception as e:
                    logger.error(f"处理图片失败: {e}")
            elif isinstance(comp, Record):
                try:
                    file_path = await comp.convert_to_file_path()
                    await self._bridge.put_output(OutputMessage(
                        msg_type="voice",
                        content=file_path,
                        session_id=self.session_id,
                        streaming=streaming
                    ))
                except Exception as e:
                    logger.error(f"处理语音失败: {e}")
            elif isinstance(comp, File):
                try:
                    file_path = await comp.get_file()
                    await self._bridge.put_output(OutputMessage(
                        msg_type="file",
                        content=file_path,
                        session_id=self.session_id,
                        streaming=streaming,
                        metadata={"filename": comp.name}
                    ))
                except Exception as e:
                    logger.error(f"处理文件失败: {e}")


# ============================================================================
# 平台适配器
# ============================================================================

@register_platform_adapter(
    adapter_name="desktop_assistant",
    desc="桌面悬浮球助手 - 提供可拖拽的悬浮球界面、多模态对话窗口、桌面感知和主动对话功能",
    default_config_tmpl={
        "type": "desktop_assistant",
        "enable": True,
        "id": "desktop_assistant",
        # 外观配置
        "avatar_path": "",
        "ball_size": 64,
        "ball_opacity": 0.9,
        "theme": "auto",
        # 对话窗口配置
        "window_width": 400,
        "window_height": 600,
        "font_size": 14,
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
        # 语音配置
        "enable_tts": True,
        "auto_play_voice": False,
    },
    adapter_display_name="桌面悬浮球助手",
    logo_path="gui/resources/icons/logo.png",
    support_streaming_message=True
)
class DesktopAssistantAdapter(Platform):
    """桌面悬浮球助手平台适配器"""
    
    def __init__(self, platform_config: dict, event_queue: asyncio.Queue):
        super().__init__(platform_config, event_queue)
        
        self.bridge = MessageBridge()
        self.gui_thread: Optional[threading.Thread] = None
        self.gui_app = None
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
        await self._send_to_gui(message_chain, session.session_id)
        await super().send_by_session(session, message_chain)
        
    async def _send_to_gui(self, message: MessageChain, session_id: str):
        """发送消息到 GUI"""
        if not message or not message.chain:
            return
            
        for comp in message.chain:
            if isinstance(comp, Plain):
                await self.bridge.put_output(OutputMessage(
                    msg_type="text",
                    content=comp.text,
                    session_id=session_id
                ))
                
    def run(self):
        """返回适配器运行协程"""
        return self._run()
        
    async def _run(self):
        """适配器主运行协程"""
        logger.info("桌面悬浮球助手适配器启动中...")
        
        try:
            # 设置 asyncio 队列
            loop = asyncio.get_event_loop()
            self.bridge.setup_async_queues(loop)
            
            self._running = True
            self.status = self.status.__class__.RUNNING
            
            # 启动 GUI 线程
            self._start_gui_thread()
            
            # 启动桌面监控和主动对话服务
            await self._start_monitor_services()
            
            # 启动桥接和消息处理
            await asyncio.gather(
                self.bridge.start_bridge(),
                self._process_input_messages()
            )
            
        except Exception as e:
            logger.error(f"桌面悬浮球助手运行错误: {e}")
            logger.error(traceback.format_exc())
            self.record_error(str(e), traceback.format_exc())
            
    async def _start_monitor_services(self):
        """启动桌面监控和主动对话服务"""
        # 桌面监控服务
        if self.config.get("enable_desktop_monitor", True):
            self.desktop_monitor = DesktopMonitorService(
                screenshot_interval=self.config.get("monitor_interval", 60),
                proactive_min_interval=self.config.get("proactive_min_interval", 300),
                proactive_max_interval=self.config.get("proactive_max_interval", 900),
                max_screenshots=self.config.get("max_screenshots", 20),
                screenshot_max_age_hours=self.config.get("screenshot_max_age_hours", 24),
                on_state_change=self._on_desktop_state_change,
            )
            await self.desktop_monitor.start()
            logger.info("桌面监控服务已启动")
            
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
                
    async def _on_desktop_state_change(self, state: DesktopState):
        """桌面状态变化回调"""
        logger.debug(f"桌面状态更新: window={state.window_title}")
        
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
                bridge=self.bridge,
                is_proactive=True
            )
            
            self.commit_event(msg_event)
            logger.info(f"已提交主动对话事件: {message_str[:50]}...")
            
            # 通知 GUI 显示主动对话提示
            await self.bridge.put_output(OutputMessage(
                msg_type="proactive",
                content=message_str,
                session_id=self.session_id,
                metadata={
                    "trigger_type": event.trigger_type.value,
                    "screenshot_path": event.desktop_state.screenshot_path if event.has_screenshot else None
                }
            ))
            
        except Exception as e:
            logger.error(f"处理主动对话触发失败: {e}")
            logger.error(traceback.format_exc())
            
    def _start_gui_thread(self):
        """启动 GUI 线程"""
        def run_gui():
            try:
                # 延迟导入，避免在非 GUI 环境下出错
                from .gui.app import DesktopApp
                
                self.gui_app = DesktopApp(
                    config=self.config,
                    bridge=self.bridge,
                    session_id=self.session_id
                )
                self.gui_app.run()
                
            except ImportError as e:
                logger.error(f"GUI 模块导入失败: {e}")
                logger.error("请确保已安装 PySide6: pip install PySide6")
            except Exception as e:
                logger.error(f"GUI 运行错误: {e}")
                logger.error(traceback.format_exc())
                
        self.gui_thread = threading.Thread(target=run_gui, daemon=True)
        self.gui_thread.start()
        logger.info("GUI 线程已启动")
        
    async def _process_input_messages(self):
        """处理输入消息"""
        while self._running:
            try:
                msg = await self.bridge.get_input()
                await self._handle_input_message(msg)
            except Exception as e:
                logger.error(f"处理输入消息错误: {e}")
                await asyncio.sleep(0.1)
                
    async def _handle_input_message(self, msg: InputMessage):
        """处理单条输入消息"""
        try:
            # 构建 AstrBotMessage
            abm = AstrBotMessage()
            abm.self_id = "desktop_assistant"
            abm.sender = MessageMember("user", "用户")
            abm.type = MessageType.FRIEND_MESSAGE
            abm.session_id = msg.session_id
            abm.message_id = str(uuid.uuid4())
            abm.timestamp = int(msg.timestamp)
            
            # 根据消息类型构建消息链
            message_chain = []
            message_str = ""
            
            if msg.type == "text":
                message_chain.append(Plain(msg.content))
                message_str = msg.content
                
            elif msg.type == "image":
                # content 是图片文件路径
                message_chain.append(Image.fromFileSystem(msg.content))
                message_str = "[图片]"
                
            elif msg.type == "screenshot":
                # content 是截图文件路径
                message_chain.append(Image.fromFileSystem(msg.content))
                message_str = "[截图]"
                
            elif msg.type == "voice":
                # content 是语音文件路径
                message_chain.append(Record.fromFileSystem(msg.content))
                message_str = "[语音]"
                
            elif msg.type == "file":
                # content 是文件路径
                filename = msg.metadata.get("filename", os.path.basename(msg.content))
                message_chain.append(File(name=filename, file=msg.content))
                message_str = f"[文件: {filename}]"
                
            # 如果有附带的文本
            if msg.metadata.get("text"):
                message_chain.insert(0, Plain(msg.metadata["text"]))
                message_str = msg.metadata["text"] + " " + message_str
                
            abm.message = message_chain
            abm.message_str = message_str.strip()
            abm.raw_message = msg
            
            # 创建消息事件并提交
            event = DesktopMessageEvent(
                message_str=abm.message_str,
                message_obj=abm,
                platform_meta=self.metadata,
                session_id=msg.session_id,
                bridge=self.bridge
            )
            
            self.commit_event(event)
            logger.debug(f"已提交消息事件: {abm.message_str[:50]}...")
            
        except Exception as e:
            logger.error(f"处理输入消息失败: {e}")
            logger.error(traceback.format_exc())
            
            # 发送错误提示到 GUI
            await self.bridge.put_output(OutputMessage(
                msg_type="error",
                content=f"消息处理失败: {str(e)}",
                session_id=msg.session_id
            ))
            
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
        
        self.bridge.stop()
        
        # 停止 GUI
        if self.gui_app:
            try:
                self.gui_app.quit()
            except Exception as e:
                logger.error(f"停止 GUI 失败: {e}")
                
        # 等待 GUI 线程结束
        if self.gui_thread and self.gui_thread.is_alive():
            self.gui_thread.join(timeout=3)
            
        self.status = self.status.__class__.STOPPED
        logger.info("桌面悬浮球助手已停止")