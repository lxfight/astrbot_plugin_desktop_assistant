"""
对话窗口

支持多模态消息显示和输入的主对话窗口。
"""

from typing import Callable, Optional, Any

try:
    from PySide6.QtCore import Qt, Signal, QMimeData, QTimer, QUrl
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTextEdit, QPushButton, QScrollArea, QLabel,
        QFileDialog, QSplitter, QApplication, QSlider
    )
    from PySide6.QtGui import QPixmap, QIcon, QKeyEvent, QDragEnterEvent, QDropEvent, QImage, QMouseEvent
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


if HAS_PYSIDE6:
    class ChatWindow(QMainWindow):
        """对话窗口"""
        
        # 信号
        message_sent = Signal(str, object, dict)  # type, content, metadata
        
        def __init__(
            self,
            config: dict,
            session_id: str,
            on_send_message: Optional[Callable[[str, Any, dict], None]] = None,
            parent=None
        ):
            super().__init__(parent)
            
            self.config = config
            self.session_id = session_id
            self.on_send_message = on_send_message
            
            # 窗口配置
            width = config.get("window_width", 400)
            height = config.get("window_height", 600)
            
            self.setWindowTitle("AstrBot 桌面助手")
            self.setMinimumSize(300, 400)
            self.resize(width, height)
            
            # 流式消息状态
            self._streaming_message: Optional[MessageBubble] = None
            self._streaming_text = ""
            
            # 创建 UI
            self._setup_ui()
            
        def _setup_ui(self):
            """设置 UI"""
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            
            layout = QVBoxLayout(central_widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            
            # 消息列表区域
            self._message_area = QScrollArea()
            self._message_area.setWidgetResizable(True)
            self._message_area.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            
            self._message_container = QWidget()
            self._message_layout = QVBoxLayout(self._message_container)
            self._message_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self._message_layout.setSpacing(10)
            self._message_layout.setContentsMargins(10, 10, 10, 10)
            
            self._message_area.setWidget(self._message_container)
            layout.addWidget(self._message_area, 1)
            
            # 输入区域
            input_widget = self._create_input_area()
            layout.addWidget(input_widget)
            
            # 应用样式
            self._apply_styles()
            
        def _create_input_area(self) -> QWidget:
            """创建输入区域"""
            widget = QWidget()
            widget.setObjectName("inputArea")
            
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(10, 5, 10, 10)
            layout.setSpacing(5)
            
            # 工具栏
            toolbar = QHBoxLayout()
            toolbar.setSpacing(5)
            
            # 图片按钮
            self._image_btn = QPushButton("📷")
            self._image_btn.setToolTip("发送图片")
            self._image_btn.setFixedSize(32, 32)
            self._image_btn.clicked.connect(self._on_image_button)
            toolbar.addWidget(self._image_btn)
            
            # 截图按钮
            self._screenshot_btn = QPushButton("✂️")
            self._screenshot_btn.setToolTip("截图")
            self._screenshot_btn.setFixedSize(32, 32)
            self._screenshot_btn.clicked.connect(self._on_screenshot_button)
            toolbar.addWidget(self._screenshot_btn)
            
            # 语音按钮（使用自定义组件支持按住录音）
            self._voice_btn = VoiceRecordButton(self)
            self._voice_btn.setToolTip("语音输入（按住录音）")
            self._voice_btn.setFixedSize(32, 32)
            self._voice_btn.recording_finished.connect(self._on_voice_recording_finished)
            toolbar.addWidget(self._voice_btn)
            
            # 文件按钮
            self._file_btn = QPushButton("📎")
            self._file_btn.setToolTip("发送文件")
            self._file_btn.setFixedSize(32, 32)
            self._file_btn.clicked.connect(self._on_file_button)
            toolbar.addWidget(self._file_btn)
            
            toolbar.addStretch()
            layout.addLayout(toolbar)
            
            # 输入框和发送按钮
            input_row = QHBoxLayout()
            input_row.setSpacing(5)
            
            self._text_input = ChatInputTextEdit(self)
            self._text_input.setPlaceholderText("输入消息... (Ctrl+Enter 发送)")
            self._text_input.setMaximumHeight(100)
            self._text_input.setAcceptDrops(True)
            self._text_input.send_requested.connect(self._on_send_button)
            self._text_input.image_pasted.connect(self._on_image_pasted)
            self._text_input.file_dropped.connect(self._on_file_dropped)
            input_row.addWidget(self._text_input, 1)
            
            self._send_btn = QPushButton("发送")
            self._send_btn.setFixedWidth(60)
            self._send_btn.clicked.connect(self._on_send_button)
            input_row.addWidget(self._send_btn)
            
            layout.addLayout(input_row)
            
            return widget
            
        def _apply_styles(self):
            """应用样式"""
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #f5f5f5;
                }
                #inputArea {
                    background-color: white;
                    border-top: 1px solid #ddd;
                }
                QTextEdit {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 5px;
                    font-size: 14px;
                }
                QPushButton {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    background-color: white;
                }
                QPushButton:hover {
                    background-color: #f0f0f0;
                }
                QPushButton:pressed {
                    background-color: #e0e0e0;
                }
            """)
            
        def _on_send_button(self):
            """发送按钮点击"""
            text = self._text_input.toPlainText().strip()
            if text:
                self._send_text_message(text)
                self._text_input.clear()
                
        def _send_text_message(self, text: str):
            """发送文本消息"""
            if self.on_send_message:
                self.on_send_message("text", text, {})
                
        def _on_image_button(self):
            """图片按钮点击"""
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择图片", "",
                "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
            )
            if file_path and self.on_send_message:
                self.on_send_message("image", file_path, {})
                
        def _on_screenshot_button(self):
            """截图按钮点击 - 区域截图"""
            try:
                from ..screenshot_selector import RegionScreenshotCapture
                
                # 隐藏窗口
                self.hide()
                
                # 延迟执行以确保窗口隐藏
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self._start_region_screenshot)
            except ImportError:
                # 回退到全屏截图
                self._do_full_screenshot()
                
        def _start_region_screenshot(self):
            """开始区域截图"""
            try:
                from ..screenshot_selector import RegionScreenshotCapture
                
                self._capture = RegionScreenshotCapture()
                self._capture.capture_async(self._on_region_screenshot_complete)
            except Exception as e:
                self.add_system_message(f"区域截图失败: {e}")
                self.show()
                
        def _on_region_screenshot_complete(self, screenshot_path):
            """区域截图完成"""
            self.show()
            if screenshot_path and self.on_send_message:
                self.on_send_message("screenshot", screenshot_path, {})
                
        def _do_full_screenshot(self):
            """执行全屏截图"""
            try:
                from ...services.screen_capture import ScreenCaptureService
                service = ScreenCaptureService()
                screenshot_path = service.capture_full_screen_to_file()
                if screenshot_path and self.on_send_message:
                    self.on_send_message("screenshot", screenshot_path, {})
            except Exception as e:
                self.add_system_message(f"截图失败: {e}")
                
        def _on_image_pasted(self, image_path: str):
            """处理粘贴的图片"""
            if self.on_send_message:
                self.on_send_message("image", image_path, {})
                
        def _on_file_dropped(self, file_path: str):
            """处理拖放的文件"""
            import os
            
            # 检查是否是图片
            image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext in image_extensions:
                if self.on_send_message:
                    self.on_send_message("image", file_path, {})
            else:
                if self.on_send_message:
                    filename = os.path.basename(file_path)
                    self.on_send_message("file", file_path, {"filename": filename})
                
        def _on_file_button(self):
            """文件按钮点击"""
            file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "")
            if file_path and self.on_send_message:
                import os
                filename = os.path.basename(file_path)
                self.on_send_message("file", file_path, {"filename": filename})
                
        # ======== 消息显示方法 ========
        
        def add_text_message(self, text: str, is_user: bool, streaming: bool = False):
            """添加文本消息"""
            if streaming and not is_user:
                # 流式消息
                if self._streaming_message is None:
                    self._streaming_message = MessageBubble("", is_user=False)
                    self._message_layout.addWidget(self._streaming_message)
                    self._streaming_text = ""
                self._streaming_text += text
                self._streaming_message.set_text(self._streaming_text)
            else:
                bubble = MessageBubble(text, is_user=is_user)
                self._message_layout.addWidget(bubble)
                
            self._scroll_to_bottom()
            
        def add_image_message(self, image_path: str, is_user: bool):
            """添加图片消息"""
            bubble = ImageBubble(image_path, is_user=is_user)
            self._message_layout.addWidget(bubble)
            self._scroll_to_bottom()
            
        def add_voice_message(self, audio_path: str, is_user: bool):
            """添加语音消息"""
            bubble = VoiceBubble(audio_path, is_user=is_user)
            self._message_layout.addWidget(bubble)
            self._scroll_to_bottom()
            
        def add_file_message(self, file_path: str, filename: str, is_user: bool):
            """添加文件消息"""
            bubble = FileBubble(file_path, filename, is_user=is_user)
            self._message_layout.addWidget(bubble)
            self._scroll_to_bottom()
            
        def add_system_message(self, text: str):
            """添加系统消息"""
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("""
                QLabel {
                    color: #888;
                    font-size: 12px;
                    padding: 5px;
                }
            """)
            self._message_layout.addWidget(label)
            self._scroll_to_bottom()
            
        def finish_streaming_message(self):
            """完成流式消息"""
            self._streaming_message = None
            self._streaming_text = ""
            
        def _scroll_to_bottom(self):
            """滚动到底部"""
            scrollbar = self._message_area.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
        def _on_voice_recording_finished(self, audio_path: str):
            """语音录制完成"""
            if audio_path and self.on_send_message:
                self.on_send_message("voice", audio_path, {})


    class ChatInputTextEdit(QTextEdit):
        """自定义输入框，支持快捷键和拖放"""
        
        # 信号
        send_requested = Signal()
        image_pasted = Signal(str)  # 图片路径
        file_dropped = Signal(str)  # 文件路径
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAcceptDrops(True)
            
            # 临时目录
            import os
            self._temp_dir = "./temp/clipboard"
            os.makedirs(self._temp_dir, exist_ok=True)
            
        def keyPressEvent(self, event: QKeyEvent):
            """键盘事件"""
            # Ctrl+Enter 发送消息
            if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.send_requested.emit()
                event.accept()
                return
                
            # Ctrl+V 粘贴（检查剪贴板是否有图片）
            if event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                if self._try_paste_image():
                    event.accept()
                    return
                    
            super().keyPressEvent(event)
            
        def _try_paste_image(self) -> bool:
            """尝试从剪贴板粘贴图片，成功返回 True"""
            clipboard = QApplication.clipboard()
            mimeData = clipboard.mimeData()
            
            # 检查是否有图片
            if mimeData.hasImage():
                image = clipboard.image()
                if not image.isNull():
                    # 保存图片到临时文件
                    import time
                    filename = f"clipboard_{int(time.time() * 1000)}.png"
                    filepath = f"{self._temp_dir}/{filename}"
                    
                    if image.save(filepath, "PNG"):
                        self.image_pasted.emit(filepath)
                        return True
                        
            # 检查是否有图片文件 URL
            if mimeData.hasUrls():
                for url in mimeData.urls():
                    if url.isLocalFile():
                        file_path = url.toLocalFile()
                        import os
                        ext = os.path.splitext(file_path)[1].lower()
                        if ext in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}:
                            self.image_pasted.emit(file_path)
                            return True
                            
            return False
            
        def dragEnterEvent(self, event: QDragEnterEvent):
            """拖拽进入事件"""
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                super().dragEnterEvent(event)
                
        def dropEvent(self, event: QDropEvent):
            """拖放事件"""
            mimeData = event.mimeData()
            
            if mimeData.hasUrls():
                for url in mimeData.urls():
                    if url.isLocalFile():
                        file_path = url.toLocalFile()
                        self.file_dropped.emit(file_path)
                        event.acceptProposedAction()
                        return
                        
            super().dropEvent(event)


    class MessageBubble(QWidget):
        """消息气泡"""
        
        def __init__(self, text: str, is_user: bool, parent=None):
            super().__init__(parent)
            
            self.is_user = is_user
            
            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            
            self._label = QLabel(text)
            self._label.setWordWrap(True)
            self._label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            
            if is_user:
                layout.addStretch()
                self._label.setStyleSheet("""
                    QLabel {
                        background-color: #0084ff;
                        color: white;
                        border-radius: 10px;
                        padding: 10px;
                        font-size: 14px;
                    }
                """)
            else:
                self._label.setStyleSheet("""
                    QLabel {
                        background-color: white;
                        color: black;
                        border-radius: 10px;
                        padding: 10px;
                        font-size: 14px;
                        border: 1px solid #ddd;
                    }
                """)
                
            layout.addWidget(self._label)
            
            if not is_user:
                layout.addStretch()
                
        def set_text(self, text: str):
            """设置文本"""
            self._label.setText(text)


    class ImageBubble(QWidget):
        """图片消息气泡"""
        
        def __init__(self, image_path: str, is_user: bool, parent=None):
            super().__init__(parent)
            
            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            
            label = QLabel()
            pixmap = QPixmap(image_path)
            if pixmap.width() > 200:
                pixmap = pixmap.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(pixmap)
            label.setStyleSheet("border-radius: 10px;")
            
            if is_user:
                layout.addStretch()
            layout.addWidget(label)
            if not is_user:
                layout.addStretch()


    class VoiceRecordButton(QPushButton):
        """语音录制按钮 - 按住录音"""
        
        # 信号
        recording_finished = Signal(str)  # 录制完成，发送音频路径
        
        def __init__(self, parent=None):
            super().__init__("🎤", parent)
            
            self._is_recording = False
            self._recorder = None
            self._record_timer = QTimer(self)
            self._record_timer.timeout.connect(self._update_recording_time)
            self._record_start_time = 0.0
            
            # 正常样式
            self._normal_style = """
                QPushButton {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    background-color: white;
                }
                QPushButton:hover {
                    background-color: #f0f0f0;
                }
            """
            # 录制中样式
            self._recording_style = """
                QPushButton {
                    border: 2px solid #ff4444;
                    border-radius: 5px;
                    background-color: #ffcccc;
                    color: #ff0000;
                }
            """
            self.setStyleSheet(self._normal_style)
            
        def mousePressEvent(self, event: QMouseEvent):
            """鼠标按下 - 开始录音"""
            if event.button() == Qt.MouseButton.LeftButton:
                self._start_recording()
            super().mousePressEvent(event)
            
        def mouseReleaseEvent(self, event: QMouseEvent):
            """鼠标释放 - 停止录音"""
            if event.button() == Qt.MouseButton.LeftButton and self._is_recording:
                self._stop_recording()
            super().mouseReleaseEvent(event)
            
        def _start_recording(self):
            """开始录音"""
            try:
                from ...services.audio_recorder import AudioRecorderService
                
                self._recorder = AudioRecorderService()
                if self._recorder.start_recording():
                    self._is_recording = True
                    self._record_start_time = 0.0
                    self.setStyleSheet(self._recording_style)
                    self.setText("🔴 0s")
                    self._record_timer.start(100)  # 每100ms更新一次
            except ImportError as e:
                print(f"录音服务不可用: {e}")
            except Exception as e:
                print(f"开始录音失败: {e}")
                
        def _stop_recording(self):
            """停止录音"""
            self._record_timer.stop()
            self._is_recording = False
            self.setStyleSheet(self._normal_style)
            self.setText("🎤")
            
            if self._recorder:
                try:
                    audio_path = self._recorder.stop_recording(save_to_file=True)
                    if audio_path:
                        self.recording_finished.emit(audio_path)
                except Exception as e:
                    print(f"停止录音失败: {e}")
                finally:
                    self._recorder = None
                    
        def _update_recording_time(self):
            """更新录制时长显示"""
            if self._recorder and self._is_recording:
                duration = self._recorder.recording_duration
                self.setText(f"🔴 {int(duration)}s")


    class VoiceBubble(QWidget):
        """语音消息气泡 - 支持播放"""
        
        def __init__(self, audio_path: str, is_user: bool, parent=None):
            super().__init__(parent)
            
            self.audio_path = audio_path
            self.is_user = is_user
            self._is_playing = False
            
            # 音频播放器
            self._player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._player.setAudioOutput(self._audio_output)
            self._audio_output.setVolume(1.0)
            
            # 连接信号
            self._player.playbackStateChanged.connect(self._on_playback_state_changed)
            self._player.positionChanged.connect(self._on_position_changed)
            self._player.durationChanged.connect(self._on_duration_changed)
            
            # 主布局
            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            
            # 气泡容器
            self._bubble = QWidget()
            bubble_layout = QHBoxLayout(self._bubble)
            bubble_layout.setContentsMargins(10, 8, 10, 8)
            bubble_layout.setSpacing(8)
            
            # 播放按钮
            self._play_btn = QPushButton("▶")
            self._play_btn.setFixedSize(28, 28)
            self._play_btn.clicked.connect(self._toggle_play)
            self._play_btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    border-radius: 14px;
                    background-color: rgba(0,0,0,0.1);
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(0,0,0,0.2);
                }
            """)
            bubble_layout.addWidget(self._play_btn)
            
            # 进度条
            self._progress = QSlider(Qt.Orientation.Horizontal)
            self._progress.setFixedWidth(80)
            self._progress.setRange(0, 100)
            self._progress.setValue(0)
            self._progress.sliderMoved.connect(self._on_slider_moved)
            self._progress.setStyleSheet("""
                QSlider::groove:horizontal {
                    height: 4px;
                    background: rgba(0,0,0,0.1);
                    border-radius: 2px;
                }
                QSlider::handle:horizontal {
                    width: 12px;
                    height: 12px;
                    margin: -4px 0;
                    background: #666;
                    border-radius: 6px;
                }
                QSlider::sub-page:horizontal {
                    background: #0084ff;
                    border-radius: 2px;
                }
            """)
            bubble_layout.addWidget(self._progress)
            
            # 时长标签
            self._duration_label = QLabel("0:00")
            self._duration_label.setStyleSheet("font-size: 11px; color: #666;")
            bubble_layout.addWidget(self._duration_label)
            
            # 应用气泡样式
            if is_user:
                self._bubble.setStyleSheet("""
                    QWidget {
                        background-color: #0084ff;
                        border-radius: 12px;
                    }
                    QLabel {
                        color: white;
                    }
                """)
                self._play_btn.setStyleSheet("""
                    QPushButton {
                        border: none;
                        border-radius: 14px;
                        background-color: rgba(255,255,255,0.2);
                        color: white;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255,255,255,0.3);
                    }
                """)
            else:
                self._bubble.setStyleSheet("""
                    QWidget {
                        background-color: white;
                        border: 1px solid #ddd;
                        border-radius: 12px;
                    }
                """)
            
            if is_user:
                layout.addStretch()
            layout.addWidget(self._bubble)
            if not is_user:
                layout.addStretch()
                
            # 加载音频
            self._player.setSource(QUrl.fromLocalFile(audio_path))
            
        def _toggle_play(self):
            """切换播放/暂停"""
            if self._is_playing:
                self._player.pause()
            else:
                self._player.play()
                
        def _on_playback_state_changed(self, state):
            """播放状态变化"""
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self._is_playing = True
                self._play_btn.setText("⏸")
            else:
                self._is_playing = False
                self._play_btn.setText("▶")
                if state == QMediaPlayer.PlaybackState.StoppedState:
                    self._progress.setValue(0)
                    
        def _on_position_changed(self, position: int):
            """播放位置变化"""
            duration = self._player.duration()
            if duration > 0:
                progress = int(position / duration * 100)
                self._progress.setValue(progress)
                
        def _on_duration_changed(self, duration: int):
            """时长变化"""
            seconds = duration // 1000
            self._duration_label.setText(f"{seconds // 60}:{seconds % 60:02d}")
            
        def _on_slider_moved(self, value: int):
            """滑块移动"""
            duration = self._player.duration()
            if duration > 0:
                position = int(value / 100 * duration)
                self._player.setPosition(position)


    class FileBubble(QWidget):
        """文件消息气泡"""
        
        def __init__(self, file_path: str, filename: str, is_user: bool, parent=None):
            super().__init__(parent)
            
            self.file_path = file_path
            
            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            
            btn = QPushButton(f"📄 {filename}")
            btn.clicked.connect(self._open_file)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #ddd;
                    border-radius: 10px;
                    padding: 10px 20px;
                }
            """)
            
            if is_user:
                layout.addStretch()
            layout.addWidget(btn)
            if not is_user:
                layout.addStretch()
                
        def _open_file(self):
            """打开文件"""
            import os
            import subprocess
            import sys
            
            if sys.platform == "win32":
                os.startfile(self.file_path)
            elif sys.platform == "darwin":
                subprocess.call(["open", self.file_path])
            else:
                subprocess.call(["xdg-open", self.file_path])

else:
    # PySide6 未安装时的占位类
    class ChatWindow:
        def __init__(self, *args, **kwargs):
            raise ImportError("PySide6 未安装")