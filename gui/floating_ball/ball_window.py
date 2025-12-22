"""
悬浮球窗口

提供可拖拽的圆形悬浮窗口，支持：
- 自定义头像
- 单击显示气泡对话
- 双击打开对话窗口
- 右键菜单
"""

from typing import Callable, Optional

try:
    from PySide6.QtCore import Qt, QPoint, QTimer, Signal
    from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QMouseEvent
    from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QMenu
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


if HAS_PYSIDE6:
    class FloatingBallWindow(QWidget):
        """悬浮球窗口"""
        
        # 信号
        clicked = Signal()
        double_clicked = Signal()
        settings_requested = Signal()
        
        def __init__(
            self,
            config: dict,
            on_open_chat: Optional[Callable] = None,
            on_send_text: Optional[Callable[[str], None]] = None,
            on_open_settings: Optional[Callable] = None,
            parent=None
        ):
            super().__init__(parent)
            
            self.config = config
            self.on_open_chat = on_open_chat
            self.on_send_text = on_send_text
            self.on_open_settings = on_open_settings
            
            # 配置参数
            self.ball_size = config.get("ball_size", 64)
            self.ball_opacity = config.get("ball_opacity", 0.9)
            avatar_path = config.get("avatar_path", "")
            
            # 窗口属性
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setFixedSize(self.ball_size, self.ball_size)
            
            # 拖拽状态
            self._dragging = False
            self._drag_start_pos = QPoint()
            self._click_timer = QTimer()
            self._click_timer.setSingleShot(True)
            self._click_timer.timeout.connect(self._on_single_click)
            self._pending_click = False
            
            # 创建头像标签
            self._avatar_label = QLabel(self)
            self._avatar_label.setFixedSize(self.ball_size, self.ball_size)
            self._avatar_label.setScaledContents(True)
            
            # 加载头像
            self._load_avatar(avatar_path)
            
            # 气泡对话
            self._bubble_widget: Optional[BubbleWidget] = None
            
            # 初始位置（屏幕右侧中间）
            self._move_to_default_position()
            
        def _load_avatar(self, avatar_path: str):
            """加载头像图片"""
            import os
            
            pixmap = None
            if avatar_path and os.path.exists(avatar_path):
                pixmap = QPixmap(avatar_path)
            else:
                # 使用默认头像（简单的圆形）
                pixmap = self._create_default_avatar()
                
            if pixmap:
                # 裁剪为圆形
                circular_pixmap = self._make_circular(pixmap)
                self._avatar_label.setPixmap(circular_pixmap)
                
        def _create_default_avatar(self) -> QPixmap:
            """创建默认头像"""
            pixmap = QPixmap(self.ball_size, self.ball_size)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 绘制渐变圆形
            gradient_color = QColor(100, 149, 237)  # 矢车菊蓝
            painter.setBrush(QBrush(gradient_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, self.ball_size, self.ball_size)
            
            # 绘制简单的机器人图标
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPixelSize(self.ball_size // 2)
            painter.setFont(font)
            painter.drawText(
                pixmap.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "🤖"
            )
            
            painter.end()
            return pixmap
            
        def _make_circular(self, pixmap: QPixmap) -> QPixmap:
            """将图片裁剪为圆形"""
            size = min(pixmap.width(), pixmap.height())
            scaled = pixmap.scaled(
                self.ball_size, self.ball_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            
            circular = QPixmap(self.ball_size, self.ball_size)
            circular.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(circular)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 创建圆形裁剪区域
            path = painter.clipPath()
            painter.setBrush(QBrush(scaled))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, self.ball_size, self.ball_size)
            
            painter.end()
            return circular
            
        def _move_to_default_position(self):
            """移动到默认位置"""
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                geometry = screen.availableGeometry()
                x = geometry.right() - self.ball_size - 20
                y = geometry.center().y() - self.ball_size // 2
                self.move(x, y)
                
        def mousePressEvent(self, event: QMouseEvent):
            """鼠标按下事件"""
            if event.button() == Qt.MouseButton.LeftButton:
                self._dragging = True
                self._drag_start_pos = event.globalPosition().toPoint() - self.pos()
                event.accept()
            elif event.button() == Qt.MouseButton.RightButton:
                self._show_context_menu(event.globalPosition().toPoint())
                event.accept()
                
        def mouseMoveEvent(self, event: QMouseEvent):
            """鼠标移动事件"""
            if self._dragging:
                new_pos = event.globalPosition().toPoint() - self._drag_start_pos
                self.move(new_pos)
                event.accept()
                
        def mouseReleaseEvent(self, event: QMouseEvent):
            """鼠标释放事件"""
            if event.button() == Qt.MouseButton.LeftButton:
                if self._dragging:
                    # 检查是否是点击（移动距离很小）
                    move_distance = (event.globalPosition().toPoint() - 
                                   (self._drag_start_pos + self.pos())).manhattanLength()
                    if move_distance < 5:
                        # 处理点击
                        self._pending_click = True
                        self._click_timer.start(250)  # 250ms 区分单击和双击
                self._dragging = False
                event.accept()
                
        def mouseDoubleClickEvent(self, event: QMouseEvent):
            """鼠标双击事件"""
            if event.button() == Qt.MouseButton.LeftButton:
                self._pending_click = False
                self._click_timer.stop()
                self.double_clicked.emit()
                if self.on_open_chat:
                    self.on_open_chat()
                event.accept()
                
        def _on_single_click(self):
            """处理单击"""
            if self._pending_click:
                self._pending_click = False
                self.clicked.emit()
                # 可以显示一个简短的气泡或提示
                
        def _show_context_menu(self, pos: QPoint):
            """显示右键菜单"""
            menu = QMenu(self)
            
            # 打开对话
            open_chat_action = menu.addAction("💬 打开对话")
            open_chat_action.triggered.connect(self._on_open_chat_action)
            
            menu.addSeparator()
            
            # 截图功能
            region_screenshot_action = menu.addAction("✂️ 区域截图")
            region_screenshot_action.triggered.connect(self._on_region_screenshot)
            
            full_screenshot_action = menu.addAction("🖥️ 全屏截图")
            full_screenshot_action.triggered.connect(self._on_full_screenshot)
            
            menu.addSeparator()
            
            # 设置
            settings_action = menu.addAction("⚙️ 设置")
            settings_action.triggered.connect(self._on_settings)
            
            menu.addSeparator()
            
            # 隐藏悬浮球
            hide_action = menu.addAction("👁️ 隐藏悬浮球")
            hide_action.triggered.connect(self.hide)
            
            # 退出应用
            quit_action = menu.addAction("❌ 退出")
            quit_action.triggered.connect(self._on_quit_action)
            
            menu.exec(pos)
            
        def _on_open_chat_action(self):
            """打开对话菜单项"""
            if self.on_open_chat:
                self.on_open_chat()
                
        def _on_region_screenshot(self):
            """区域截图"""
            try:
                from ..screenshot_selector import RegionScreenshotCapture
                
                # 隐藏悬浮球
                self.hide()
                
                # 延迟执行以确保悬浮球完全隐藏
                QTimer.singleShot(100, self._start_region_capture)
            except ImportError as e:
                print(f"区域截图功能不可用: {e}")
                
        def _start_region_capture(self):
            """开始区域截图"""
            try:
                from ..screenshot_selector import RegionScreenshotCapture
                
                self._capture = RegionScreenshotCapture()
                self._capture.capture_async(self._on_screenshot_complete)
            except Exception as e:
                print(f"启动区域截图失败: {e}")
                self.show()
                
        def _on_full_screenshot(self):
            """全屏截图"""
            try:
                from ...services.screen_capture import ScreenCaptureService
                
                # 隐藏悬浮球
                self.hide()
                
                # 延迟执行以确保悬浮球完全隐藏
                QTimer.singleShot(100, self._do_full_screenshot)
            except ImportError as e:
                print(f"截图功能不可用: {e}")
                
        def _do_full_screenshot(self):
            """执行全屏截图"""
            try:
                from ...services.screen_capture import ScreenCaptureService
                
                service = ScreenCaptureService()
                screenshot_path = service.capture_full_screen_to_file()
                
                self.show()
                
                if screenshot_path and self.on_send_text:
                    # 通过消息桥发送截图
                    self._send_screenshot(screenshot_path)
            except Exception as e:
                print(f"全屏截图失败: {e}")
                self.show()
                
        def _on_screenshot_complete(self, screenshot_path):
            """截图完成回调"""
            self.show()
            
            if screenshot_path:
                self._send_screenshot(screenshot_path)
                
        def _send_screenshot(self, screenshot_path: str):
            """发送截图到对话"""
            # 打开对话窗口并发送截图
            if self.on_open_chat:
                self.on_open_chat()
            # 截图将通过 on_send_text 回调处理
            # 这里需要通过 app 层面来处理图片发送
            
        def _on_settings(self):
            """打开设置窗口"""
            self.settings_requested.emit()
            if self.on_open_settings:
                self.on_open_settings()
            
        def _on_quit_action(self):
            """退出应用"""
            from PySide6.QtWidgets import QApplication
            QApplication.quit()
                
        def show_bubble(self, text: str, duration: int = 3000, is_proactive: bool = False):
            """
            显示气泡对话
            
            Args:
                text: 显示的文本
                duration: 显示持续时间（毫秒）
                is_proactive: 是否为主动对话（使用特殊样式）
            """
            if self._bubble_widget is None:
                self._bubble_widget = BubbleWidget(self)
                
            self._bubble_widget.show_message(text, duration, is_proactive)
            
            # 定位气泡在悬浮球左侧
            bubble_x = self.x() - self._bubble_widget.width() - 10
            bubble_y = self.y() + (self.height() - self._bubble_widget.height()) // 2
            self._bubble_widget.move(bubble_x, bubble_y)
            self._bubble_widget.show()


    class BubbleWidget(QWidget):
        """气泡对话组件"""
        
        # 普通样式
        NORMAL_STYLE = """
            QLabel {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 10px;
                padding: 10px;
                font-size: 13px;
                color: #333;
            }
        """
        
        # 主动对话样式（带有渐变边框）
        PROACTIVE_STYLE = """
            QLabel {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f0f8ff, stop:1 #e6f3ff
                );
                border: 2px solid #6495ED;
                border-radius: 12px;
                padding: 12px;
                font-size: 13px;
                color: #2c5282;
            }
        """
        
        def __init__(self, parent=None):
            super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool
            )
            
            self._label = QLabel(self)
            self._label.setWordWrap(True)
            self._label.setMaximumWidth(250)
            self._label.setStyleSheet(self.NORMAL_STYLE)
            
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._label)
            
            self._hide_timer = QTimer(self)
            self._hide_timer.setSingleShot(True)
            self._hide_timer.timeout.connect(self.hide)
            
        def show_message(self, text: str, duration: int = 3000, is_proactive: bool = False):
            """
            显示消息
            
            Args:
                text: 显示的文本
                duration: 显示持续时间（毫秒）
                is_proactive: 是否为主动对话样式
            """
            # 根据类型设置样式
            if is_proactive:
                self._label.setStyleSheet(self.PROACTIVE_STYLE)
                # 主动对话显示更长时间
                duration = max(duration, 5000)
            else:
                self._label.setStyleSheet(self.NORMAL_STYLE)
                
            self._label.setText(text)
            self.adjustSize()
            self._hide_timer.start(duration)

else:
    # PySide6 未安装时的占位类
    class FloatingBallWindow:
        def __init__(self, *args, **kwargs):
            raise ImportError("PySide6 未安装")
            
    class BubbleWidget:
        def __init__(self, *args, **kwargs):
            raise ImportError("PySide6 未安装")