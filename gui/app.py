"""
桌面悬浮球助手 - Qt 应用主类

负责管理 Qt 应用生命周期、悬浮球窗口和对话窗口。
"""

import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..main import MessageBridge, OutputMessage

try:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


class DesktopApp:
    """桌面助手 Qt 应用"""
    
    def __init__(
        self,
        config: dict,
        bridge: "MessageBridge",
        session_id: str
    ):
        if not HAS_PYSIDE6:
            raise ImportError("PySide6 未安装，请运行: pip install PySide6")
            
        self.config = config
        self.bridge = bridge
        self.session_id = session_id
        
        self.app: Optional[QApplication] = None
        self.floating_ball = None
        self.chat_window = None
        self.system_tray = None
        self.settings_window = None
        self._poll_timer: Optional[QTimer] = None
        
    def run(self):
        """启动 Qt 应用"""
        # 创建 QApplication（如果不存在）
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
            
        # 设置应用属性
        self.app.setQuitOnLastWindowClosed(False)
        
        # 创建悬浮球窗口
        from .floating_ball.ball_window import FloatingBallWindow
        self.floating_ball = FloatingBallWindow(
            config=self.config,
            on_open_chat=self._open_chat_window,
            on_send_text=self._send_text_message,
            on_open_settings=self._open_settings_window
        )
        self.floating_ball.show()
        
        # 创建对话窗口（初始隐藏）
        from .chat_window.chat_window import ChatWindow
        self.chat_window = ChatWindow(
            config=self.config,
            session_id=self.session_id,
            on_send_message=self._on_message_from_gui
        )
        
        # 创建系统托盘
        from .system_tray import SystemTrayManager
        self.system_tray = SystemTrayManager(
            config=self.config,
            on_show_ball=self._show_floating_ball,
            on_hide_ball=self._hide_floating_ball,
            on_open_chat=self._open_chat_window,
            on_open_settings=self._open_settings_window,
            on_quit=self.quit
        )
        self.system_tray.show()
        
        # 启动输出消息轮询
        self._start_output_polling()
        
        # 运行事件循环
        self.app.exec()
        
    def quit(self):
        """退出应用"""
        if self._poll_timer:
            self._poll_timer.stop()
        if self.system_tray:
            self.system_tray.hide()
        if self.app:
            self.app.quit()
            
    def _show_floating_ball(self):
        """显示悬浮球"""
        if self.floating_ball:
            self.floating_ball.show()
            
    def _hide_floating_ball(self):
        """隐藏悬浮球"""
        if self.floating_ball:
            self.floating_ball.hide()
            
    def _start_output_polling(self):
        """启动输出消息轮询定时器"""
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_output_messages)
        self._poll_timer.start(50)  # 50ms 轮询间隔
        
    def _poll_output_messages(self):
        """轮询输出消息队列"""
        # 每次最多处理 10 条消息，避免阻塞 UI
        for _ in range(10):
            msg = self.bridge.get_output()
            if msg is None:
                break
            self._handle_output_message(msg)
            
    def _handle_output_message(self, msg: "OutputMessage"):
        """处理输出消息"""
        if self.chat_window is None:
            return
            
        if msg.type == "text":
            self.chat_window.add_text_message(
                text=msg.content,
                is_user=False,
                streaming=msg.streaming
            )
            # 同时在悬浮球显示气泡
            if self.floating_ball and not msg.streaming:
                preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                self.floating_ball.show_bubble(preview)
                
        elif msg.type == "image":
            self.chat_window.add_image_message(
                image_path=msg.content,
                is_user=False
            )
            
        elif msg.type == "voice":
            self.chat_window.add_voice_message(
                audio_path=msg.content,
                is_user=False
            )
            
        elif msg.type == "file":
            filename = msg.metadata.get("filename", "文件")
            self.chat_window.add_file_message(
                file_path=msg.content,
                filename=filename,
                is_user=False
            )
            
        elif msg.type == "error":
            self.chat_window.add_system_message(f"错误: {msg.content}")
            
        elif msg.type == "end":
            self.chat_window.finish_streaming_message()
            
        elif msg.type == "proactive":
            # 主动对话触发
            self._handle_proactive_message(msg)
            
    def _handle_proactive_message(self, msg: "OutputMessage"):
        """处理主动对话消息"""
        trigger_type = msg.metadata.get("trigger_type", "random")
        screenshot_path = msg.metadata.get("screenshot_path")
        
        # 在悬浮球显示主动对话气泡
        if self.floating_ball:
            preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
            self.floating_ball.show_bubble(preview, is_proactive=True)
            
        # 添加系统消息到对话窗口
        if self.chat_window:
            trigger_label = {
                "random": "💬 主动问候",
                "window": "👀 桌面感知",
                "scheduled": "⏰ 定时提醒",
                "idle": "😴 空闲检测"
            }.get(trigger_type, "💬 主动对话")
            
            self.chat_window.add_system_message(f"[{trigger_label}]")
            self.chat_window.add_text_message(
                text=msg.content,
                is_user=False,
                streaming=False
            )
            
            # 如果有截图，也添加到对话窗口
            if screenshot_path:
                self.chat_window.add_image_message(
                    image_path=screenshot_path,
                    is_user=False
                )
            
    def _open_chat_window(self):
        """打开对话窗口"""
        if self.chat_window:
            self.chat_window.show()
            self.chat_window.raise_()
            self.chat_window.activateWindow()
            
    def _open_settings_window(self):
        """打开设置窗口"""
        from .settings_window import SettingsWindow
        
        if self.settings_window is None:
            self.settings_window = SettingsWindow(
                config=self.config,
                on_settings_changed=self._on_settings_changed
            )
            
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()
        
    def _on_settings_changed(self, new_config: dict):
        """设置更改回调"""
        # 更新配置
        self.config.update(new_config)
        
        # 通知各组件更新
        # 注意：部分设置需要重启才能生效
        if self.system_tray:
            self.system_tray.show_message(
                "设置已保存",
                "部分设置可能需要重启应用后生效",
                duration=3000
            )
            
    def _send_text_message(self, text: str):
        """从悬浮球发送文本消息"""
        from ..main import InputMessage
        msg = InputMessage(
            msg_type="text",
            content=text,
            session_id=self.session_id
        )
        self.bridge.put_input(msg)
        
    def _on_message_from_gui(self, msg_type: str, content, metadata: Optional[dict] = None):
        """处理来自 GUI 的消息"""
        from ..main import InputMessage
        msg = InputMessage(
            msg_type=msg_type,
            content=content,
            session_id=self.session_id,
            metadata=metadata or {}
        )
        self.bridge.put_input(msg)
        
        # 在对话窗口显示用户消息
        if self.chat_window:
            if msg_type == "text":
                self.chat_window.add_text_message(content, is_user=True)
            elif msg_type == "image" or msg_type == "screenshot":
                self.chat_window.add_image_message(content, is_user=True)
            elif msg_type == "voice":
                self.chat_window.add_voice_message(content, is_user=True)
            elif msg_type == "file":
                filename = metadata.get("filename", "文件") if metadata else "文件"
                self.chat_window.add_file_message(content, filename, is_user=True)