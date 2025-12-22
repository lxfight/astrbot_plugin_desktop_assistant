"""
系统托盘模块

提供系统托盘图标和菜单功能。
"""

from typing import Callable, Optional

try:
    from PySide6.QtCore import Qt, Signal, QObject
    from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
    from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


if HAS_PYSIDE6:
    class SystemTrayManager(QObject):
        """系统托盘管理器"""
        
        # 信号
        show_floating_ball_requested = Signal()
        hide_floating_ball_requested = Signal()
        open_chat_requested = Signal()
        open_settings_requested = Signal()
        quit_requested = Signal()
        
        def __init__(
            self,
            config: dict,
            on_show_ball: Optional[Callable] = None,
            on_hide_ball: Optional[Callable] = None,
            on_open_chat: Optional[Callable] = None,
            on_open_settings: Optional[Callable] = None,
            on_quit: Optional[Callable] = None,
            parent=None
        ):
            super().__init__(parent)
            
            self.config = config
            self.on_show_ball = on_show_ball
            self.on_hide_ball = on_hide_ball
            self.on_open_chat = on_open_chat
            self.on_open_settings = on_open_settings
            self.on_quit = on_quit
            
            self._ball_visible = True
            
            # 创建托盘图标
            self._tray_icon = QSystemTrayIcon(self)
            self._tray_icon.setIcon(self._create_tray_icon())
            self._tray_icon.setToolTip("AstrBot 桌面助手")
            
            # 创建菜单
            self._menu = self._create_menu()
            self._tray_icon.setContextMenu(self._menu)
            
            # 连接信号
            self._tray_icon.activated.connect(self._on_tray_activated)
            
        def _create_tray_icon(self) -> QIcon:
            """创建托盘图标"""
            # 创建一个简单的圆形图标
            size = 32
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 绘制圆形背景
            painter.setBrush(QColor(100, 149, 237))  # 矢车菊蓝
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(2, 2, size - 4, size - 4)
            
            # 绘制文字
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPixelSize(14)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")
            
            painter.end()
            return QIcon(pixmap)
            
        def _create_menu(self) -> QMenu:
            """创建托盘菜单"""
            menu = QMenu()
            
            # 显示/隐藏悬浮球
            self._toggle_ball_action = QAction("👁️ 隐藏悬浮球", self)
            self._toggle_ball_action.triggered.connect(self._toggle_floating_ball)
            menu.addAction(self._toggle_ball_action)
            
            menu.addSeparator()
            
            # 打开对话
            open_chat_action = QAction("💬 打开对话", self)
            open_chat_action.triggered.connect(self._on_open_chat)
            menu.addAction(open_chat_action)
            
            menu.addSeparator()
            
            # 设置
            settings_action = QAction("⚙️ 设置", self)
            settings_action.triggered.connect(self._on_open_settings)
            menu.addAction(settings_action)
            
            menu.addSeparator()
            
            # 退出
            quit_action = QAction("❌ 退出", self)
            quit_action.triggered.connect(self._on_quit)
            menu.addAction(quit_action)
            
            return menu
            
        def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
            """托盘图标激活事件"""
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                # 单击 - 切换悬浮球显示
                self._toggle_floating_ball()
            elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
                # 双击 - 打开对话窗口
                self._on_open_chat()
                
        def _toggle_floating_ball(self):
            """切换悬浮球显示状态"""
            if self._ball_visible:
                self._ball_visible = False
                self._toggle_ball_action.setText("👁️ 显示悬浮球")
                self.hide_floating_ball_requested.emit()
                if self.on_hide_ball:
                    self.on_hide_ball()
            else:
                self._ball_visible = True
                self._toggle_ball_action.setText("👁️ 隐藏悬浮球")
                self.show_floating_ball_requested.emit()
                if self.on_show_ball:
                    self.on_show_ball()
                    
        def _on_open_chat(self):
            """打开对话"""
            self.open_chat_requested.emit()
            if self.on_open_chat:
                self.on_open_chat()
                
        def _on_open_settings(self):
            """打开设置"""
            self.open_settings_requested.emit()
            if self.on_open_settings:
                self.on_open_settings()
                
        def _on_quit(self):
            """退出应用"""
            self.quit_requested.emit()
            if self.on_quit:
                self.on_quit()
                
        def show(self):
            """显示托盘图标"""
            self._tray_icon.show()
            
        def hide(self):
            """隐藏托盘图标"""
            self._tray_icon.hide()
            
        def show_message(
            self,
            title: str,
            message: str,
            icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
            duration: int = 3000
        ):
            """显示托盘通知消息"""
            self._tray_icon.showMessage(title, message, icon, duration)
            
        def set_ball_visible(self, visible: bool):
            """设置悬浮球可见状态（用于同步状态）"""
            self._ball_visible = visible
            if visible:
                self._toggle_ball_action.setText("👁️ 隐藏悬浮球")
            else:
                self._toggle_ball_action.setText("👁️ 显示悬浮球")
                
        @property
        def is_ball_visible(self) -> bool:
            """悬浮球是否可见"""
            return self._ball_visible

else:
    class SystemTrayManager:
        """占位类"""
        def __init__(self, *args, **kwargs):
            raise ImportError("PySide6 未安装")