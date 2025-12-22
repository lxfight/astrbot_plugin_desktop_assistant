"""
设置窗口

提供用户界面配置各项设置，包括：
- 外观设置（悬浮球大小、透明度、自定义头像）
- 对话窗口设置
- 桌面监控设置
- 主动对话设置
- 其他设置（开机自启动等）
"""

import os
import sys
from typing import Callable, Optional

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import (
        QCheckBox,
        QDialog,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSlider,
        QSpinBox,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


if HAS_PYSIDE6:

    class SettingsWindow(QDialog):
        """设置窗口"""

        # 信号：设置已保存
        settings_saved = Signal(dict)

        def __init__(
            self,
            config: dict,
            config_file_path: Optional[str] = None,
            on_settings_changed: Optional[Callable[[dict], None]] = None,
            parent=None,
        ):
            super().__init__(parent)

            self.config = config.copy()
            self.config_file_path = config_file_path
            self.on_settings_changed = on_settings_changed

            self._init_ui()
            self._load_config_to_ui()

        def _init_ui(self):
            """初始化 UI"""
            self.setWindowTitle("设置 - 桌面悬浮球助手")
            self.setMinimumSize(500, 600)
            self.setWindowFlags(
                self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
            )

            # 主布局
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(10, 10, 10, 10)

            # 创建标签页
            self.tab_widget = QTabWidget()
            main_layout.addWidget(self.tab_widget)

            # 外观设置页
            self.tab_widget.addTab(self._create_appearance_tab(), "🎨 外观")

            # 对话窗口设置页
            self.tab_widget.addTab(self._create_chat_window_tab(), "💬 对话窗口")

            # 桌面监控设置页
            self.tab_widget.addTab(self._create_desktop_monitor_tab(), "🖥️ 桌面监控")

            # 主动对话设置页
            self.tab_widget.addTab(self._create_proactive_dialog_tab(), "💡 主动对话")

            # 其他设置页
            self.tab_widget.addTab(self._create_other_tab(), "⚙️ 其他")

            # 底部按钮
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            self.reset_btn = QPushButton("恢复默认")
            self.reset_btn.clicked.connect(self._on_reset_defaults)
            button_layout.addWidget(self.reset_btn)

            self.cancel_btn = QPushButton("取消")
            self.cancel_btn.clicked.connect(self.reject)
            button_layout.addWidget(self.cancel_btn)

            self.save_btn = QPushButton("保存")
            self.save_btn.clicked.connect(self._on_save)
            self.save_btn.setDefault(True)
            button_layout.addWidget(self.save_btn)

            main_layout.addLayout(button_layout)

            # 设置样式
            self.setStyleSheet(self._get_stylesheet())

        def _get_stylesheet(self) -> str:
            """获取样式表"""
            return """
                QDialog {
                    background-color: #f5f5f5;
                }
                QTabWidget::pane {
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background-color: white;
                }
                QTabBar::tab {
                    padding: 8px 16px;
                    margin-right: 2px;
                    background-color: #e0e0e0;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: white;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 10px;
                    background-color: white;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QPushButton {
                    padding: 6px 16px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: white;
                }
                QPushButton:hover {
                    background-color: #e8e8e8;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
                QSpinBox, QDoubleSpinBox {
                    padding: 4px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                }
                QCheckBox {
                    spacing: 8px;
                }
                QSlider::groove:horizontal {
                    height: 6px;
                    background: #ddd;
                    border-radius: 3px;
                }
                QSlider::handle:horizontal {
                    width: 16px;
                    height: 16px;
                    margin: -5px 0;
                    background: #6495ED;
                    border-radius: 8px;
                }
                QSlider::sub-page:horizontal {
                    background: #6495ED;
                    border-radius: 3px;
                }
            """

        def _create_appearance_tab(self) -> QWidget:
            """创建外观设置页"""
            widget = QWidget()
            layout = QVBoxLayout(widget)

            # 悬浮球设置组
            ball_group = QGroupBox("悬浮球")
            ball_layout = QFormLayout(ball_group)

            # 悬浮球大小
            self.ball_size_slider = QSlider(Qt.Orientation.Horizontal)
            self.ball_size_slider.setRange(32, 128)
            self.ball_size_slider.setValue(64)
            self.ball_size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            self.ball_size_slider.setTickInterval(16)
            self.ball_size_label = QLabel("64 px")
            self.ball_size_slider.valueChanged.connect(
                lambda v: self.ball_size_label.setText(f"{v} px")
            )

            size_layout = QHBoxLayout()
            size_layout.addWidget(self.ball_size_slider)
            size_layout.addWidget(self.ball_size_label)
            ball_layout.addRow("大小：", size_layout)

            # 悬浮球透明度
            self.ball_opacity_slider = QSlider(Qt.Orientation.Horizontal)
            self.ball_opacity_slider.setRange(10, 100)
            self.ball_opacity_slider.setValue(90)
            self.ball_opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            self.ball_opacity_slider.setTickInterval(10)
            self.ball_opacity_label = QLabel("90%")
            self.ball_opacity_slider.valueChanged.connect(
                lambda v: self.ball_opacity_label.setText(f"{v}%")
            )

            opacity_layout = QHBoxLayout()
            opacity_layout.addWidget(self.ball_opacity_slider)
            opacity_layout.addWidget(self.ball_opacity_label)
            ball_layout.addRow("透明度：", opacity_layout)

            layout.addWidget(ball_group)

            # 头像设置组
            avatar_group = QGroupBox("自定义头像")
            avatar_layout = QVBoxLayout(avatar_group)

            # 头像预览
            self.avatar_preview = QLabel()
            self.avatar_preview.setFixedSize(80, 80)
            self.avatar_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.avatar_preview.setStyleSheet(
                """
                QLabel {
                    border: 2px dashed #ccc;
                    border-radius: 40px;
                    background-color: #f0f0f0;
                }
            """
            )
            self.avatar_preview.setText("无头像")

            # 头像路径
            self.avatar_path_label = QLabel("未设置")
            self.avatar_path_label.setWordWrap(True)

            # 按钮
            avatar_btn_layout = QHBoxLayout()
            self.select_avatar_btn = QPushButton("选择图片")
            self.select_avatar_btn.clicked.connect(self._on_select_avatar)
            self.clear_avatar_btn = QPushButton("清除")
            self.clear_avatar_btn.clicked.connect(self._on_clear_avatar)
            avatar_btn_layout.addWidget(self.select_avatar_btn)
            avatar_btn_layout.addWidget(self.clear_avatar_btn)
            avatar_btn_layout.addStretch()

            avatar_layout.addWidget(
                self.avatar_preview, alignment=Qt.AlignmentFlag.AlignCenter
            )
            avatar_layout.addWidget(self.avatar_path_label)
            avatar_layout.addLayout(avatar_btn_layout)

            layout.addWidget(avatar_group)

            layout.addStretch()
            return widget

        def _create_chat_window_tab(self) -> QWidget:
            """创建对话窗口设置页"""
            widget = QWidget()
            layout = QVBoxLayout(widget)

            # 窗口尺寸组
            size_group = QGroupBox("窗口尺寸")
            size_layout = QFormLayout(size_group)

            self.window_width_spin = QSpinBox()
            self.window_width_spin.setRange(300, 1200)
            self.window_width_spin.setValue(400)
            self.window_width_spin.setSuffix(" px")
            size_layout.addRow("宽度：", self.window_width_spin)

            self.window_height_spin = QSpinBox()
            self.window_height_spin.setRange(400, 1200)
            self.window_height_spin.setValue(600)
            self.window_height_spin.setSuffix(" px")
            size_layout.addRow("高度：", self.window_height_spin)

            layout.addWidget(size_group)

            # 字体设置组
            font_group = QGroupBox("字体")
            font_layout = QFormLayout(font_group)

            self.font_size_spin = QSpinBox()
            self.font_size_spin.setRange(10, 24)
            self.font_size_spin.setValue(14)
            self.font_size_spin.setSuffix(" pt")
            font_layout.addRow("字体大小：", self.font_size_spin)

            layout.addWidget(font_group)

            layout.addStretch()
            return widget

        def _create_desktop_monitor_tab(self) -> QWidget:
            """创建桌面监控设置页"""
            widget = QWidget()
            layout = QVBoxLayout(widget)

            # 基本设置组
            basic_group = QGroupBox("基本设置")
            basic_layout = QFormLayout(basic_group)

            self.enable_monitor_check = QCheckBox("启用桌面监控")
            self.enable_monitor_check.setChecked(True)
            self.enable_monitor_check.stateChanged.connect(
                self._on_monitor_enabled_changed
            )
            basic_layout.addRow("", self.enable_monitor_check)

            self.monitor_interval_spin = QSpinBox()
            self.monitor_interval_spin.setRange(10, 600)
            self.monitor_interval_spin.setValue(60)
            self.monitor_interval_spin.setSuffix(" 秒")
            basic_layout.addRow("监控间隔：", self.monitor_interval_spin)

            layout.addWidget(basic_group)

            # 截图管理组
            screenshot_group = QGroupBox("截图管理")
            screenshot_layout = QFormLayout(screenshot_group)

            self.max_screenshots_spin = QSpinBox()
            self.max_screenshots_spin.setRange(5, 100)
            self.max_screenshots_spin.setValue(20)
            screenshot_layout.addRow("最大保留数量：", self.max_screenshots_spin)

            self.screenshot_max_age_spin = QSpinBox()
            self.screenshot_max_age_spin.setRange(1, 168)
            self.screenshot_max_age_spin.setValue(24)
            self.screenshot_max_age_spin.setSuffix(" 小时")
            screenshot_layout.addRow("最长保留时间：", self.screenshot_max_age_spin)

            layout.addWidget(screenshot_group)

            # 说明
            info_label = QLabel(
                "💡 桌面监控用于记录您的桌面状态，以便 AI 助手更好地理解您的工作环境。\n"
                "截图仅保存在本地，不会上传到任何服务器。"
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color: #666; font-size: 12px; padding: 10px;")
            layout.addWidget(info_label)

            layout.addStretch()
            return widget

        def _create_proactive_dialog_tab(self) -> QWidget:
            """创建主动对话设置页"""
            widget = QWidget()

            # 使用滚动区域
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

            scroll_content = QWidget()
            layout = QVBoxLayout(scroll_content)

            # 基本设置组
            basic_group = QGroupBox("基本设置")
            basic_layout = QFormLayout(basic_group)

            self.enable_proactive_check = QCheckBox("启用主动对话")
            self.enable_proactive_check.setChecked(True)
            self.enable_proactive_check.stateChanged.connect(
                self._on_proactive_enabled_changed
            )
            basic_layout.addRow("", self.enable_proactive_check)

            layout.addWidget(basic_group)

            # 触发概率组
            probability_group = QGroupBox("触发概率")
            probability_layout = QFormLayout(probability_group)

            self.proactive_probability_slider = QSlider(Qt.Orientation.Horizontal)
            self.proactive_probability_slider.setRange(0, 100)
            self.proactive_probability_slider.setValue(30)
            self.proactive_probability_label = QLabel("30%")
            self.proactive_probability_slider.valueChanged.connect(
                lambda v: self.proactive_probability_label.setText(f"{v}%")
            )

            prob_layout = QHBoxLayout()
            prob_layout.addWidget(self.proactive_probability_slider)
            prob_layout.addWidget(self.proactive_probability_label)
            probability_layout.addRow("随机触发概率：", prob_layout)

            layout.addWidget(probability_group)

            # 时间间隔组
            interval_group = QGroupBox("时间间隔")
            interval_layout = QFormLayout(interval_group)

            self.proactive_min_interval_spin = QSpinBox()
            self.proactive_min_interval_spin.setRange(60, 3600)
            self.proactive_min_interval_spin.setValue(300)
            self.proactive_min_interval_spin.setSuffix(" 秒")
            interval_layout.addRow("最小间隔：", self.proactive_min_interval_spin)

            self.proactive_max_interval_spin = QSpinBox()
            self.proactive_max_interval_spin.setRange(120, 7200)
            self.proactive_max_interval_spin.setValue(900)
            self.proactive_max_interval_spin.setSuffix(" 秒")
            interval_layout.addRow("最大间隔：", self.proactive_max_interval_spin)

            layout.addWidget(interval_group)

            # 触发条件组
            trigger_group = QGroupBox("触发条件")
            trigger_layout = QVBoxLayout(trigger_group)

            self.window_change_check = QCheckBox("窗口变化时触发")
            self.window_change_check.setChecked(True)
            trigger_layout.addWidget(self.window_change_check)

            # 窗口变化概率
            window_prob_layout = QHBoxLayout()
            window_prob_layout.addSpacing(24)
            window_prob_layout.addWidget(QLabel("触发概率："))
            self.window_change_probability_slider = QSlider(Qt.Orientation.Horizontal)
            self.window_change_probability_slider.setRange(0, 100)
            self.window_change_probability_slider.setValue(20)
            self.window_change_probability_label = QLabel("20%")
            self.window_change_probability_slider.valueChanged.connect(
                lambda v: self.window_change_probability_label.setText(f"{v}%")
            )
            window_prob_layout.addWidget(self.window_change_probability_slider)
            window_prob_layout.addWidget(self.window_change_probability_label)
            trigger_layout.addLayout(window_prob_layout)

            self.scheduled_greetings_check = QCheckBox("定时问候")
            self.scheduled_greetings_check.setChecked(True)
            trigger_layout.addWidget(self.scheduled_greetings_check)

            layout.addWidget(trigger_group)

            # 说明
            info_label = QLabel(
                "💡 主动对话让 AI 助手能够主动与您互动，比如问候、提醒等。\n"
                "您可以根据自己的喜好调整触发概率和时间间隔。"
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color: #666; font-size: 12px; padding: 10px;")
            layout.addWidget(info_label)

            layout.addStretch()

            scroll_area.setWidget(scroll_content)

            main_layout = QVBoxLayout(widget)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.addWidget(scroll_area)

            return widget

        def _create_other_tab(self) -> QWidget:
            """创建其他设置页"""
            widget = QWidget()
            layout = QVBoxLayout(widget)

            # 语音设置组
            voice_group = QGroupBox("语音")
            voice_layout = QFormLayout(voice_group)

            self.enable_tts_check = QCheckBox("启用语音播放 (TTS)")
            self.enable_tts_check.setChecked(True)
            voice_layout.addRow("", self.enable_tts_check)

            self.auto_play_voice_check = QCheckBox("自动播放语音回复")
            self.auto_play_voice_check.setChecked(False)
            voice_layout.addRow("", self.auto_play_voice_check)

            layout.addWidget(voice_group)

            # 系统设置组
            system_group = QGroupBox("系统")
            system_layout = QFormLayout(system_group)

            self.auto_start_check = QCheckBox("开机自启动")
            self.auto_start_check.setChecked(False)
            self.auto_start_check.stateChanged.connect(self._on_auto_start_changed)
            system_layout.addRow("", self.auto_start_check)

            # 检查当前自启动状态
            self.auto_start_check.setChecked(self._check_auto_start())

            layout.addWidget(system_group)

            # 关于信息
            about_group = QGroupBox("关于")
            about_layout = QVBoxLayout(about_group)

            about_label = QLabel(
                "<b>桌面悬浮球助手</b><br>"
                "版本: 1.0.0<br>"
                "AstrBot 平台适配器插件<br><br>"
                "提供可拖拽的悬浮球界面、多模态对话窗口、<br>"
                "桌面感知和主动对话功能。"
            )
            about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            about_layout.addWidget(about_label)

            layout.addWidget(about_group)

            layout.addStretch()
            return widget

        def _load_config_to_ui(self):
            """从配置加载到 UI"""
            # 外观设置
            self.ball_size_slider.setValue(self.config.get("ball_size", 64))
            self.ball_opacity_slider.setValue(
                int(self.config.get("ball_opacity", 0.9) * 100)
            )

            avatar_path = self.config.get("avatar_path", "")
            if avatar_path and os.path.exists(avatar_path):
                self._set_avatar_preview(avatar_path)
                self.avatar_path_label.setText(avatar_path)
            else:
                self.avatar_path_label.setText("未设置")

            # 对话窗口设置
            self.window_width_spin.setValue(self.config.get("window_width", 400))
            self.window_height_spin.setValue(self.config.get("window_height", 600))
            self.font_size_spin.setValue(self.config.get("font_size", 14))

            # 桌面监控设置
            self.enable_monitor_check.setChecked(
                self.config.get("enable_desktop_monitor", True)
            )
            self.monitor_interval_spin.setValue(
                self.config.get("monitor_interval", 60)
            )
            self.max_screenshots_spin.setValue(self.config.get("max_screenshots", 20))
            self.screenshot_max_age_spin.setValue(
                self.config.get("screenshot_max_age_hours", 24)
            )

            # 主动对话设置
            self.enable_proactive_check.setChecked(
                self.config.get("enable_proactive_dialog", True)
            )
            self.proactive_probability_slider.setValue(
                int(self.config.get("proactive_probability", 0.3) * 100)
            )
            self.proactive_min_interval_spin.setValue(
                self.config.get("proactive_min_interval", 300)
            )
            self.proactive_max_interval_spin.setValue(
                self.config.get("proactive_max_interval", 900)
            )
            self.window_change_check.setChecked(
                self.config.get("window_change_enabled", True)
            )
            self.window_change_probability_slider.setValue(
                int(self.config.get("window_change_probability", 0.2) * 100)
            )
            self.scheduled_greetings_check.setChecked(
                self.config.get("scheduled_greetings_enabled", True)
            )

            # 其他设置
            self.enable_tts_check.setChecked(self.config.get("enable_tts", True))
            self.auto_play_voice_check.setChecked(
                self.config.get("auto_play_voice", False)
            )

            # 更新 UI 状态
            self._on_monitor_enabled_changed()
            self._on_proactive_enabled_changed()

        def _save_ui_to_config(self) -> dict:
            """从 UI 保存到配置"""
            config = self.config.copy()

            # 外观设置
            config["ball_size"] = self.ball_size_slider.value()
            config["ball_opacity"] = self.ball_opacity_slider.value() / 100.0
            avatar_path = self.avatar_path_label.text()
            config["avatar_path"] = avatar_path if avatar_path != "未设置" else ""

            # 对话窗口设置
            config["window_width"] = self.window_width_spin.value()
            config["window_height"] = self.window_height_spin.value()
            config["font_size"] = self.font_size_spin.value()

            # 桌面监控设置
            config["enable_desktop_monitor"] = self.enable_monitor_check.isChecked()
            config["monitor_interval"] = self.monitor_interval_spin.value()
            config["max_screenshots"] = self.max_screenshots_spin.value()
            config["screenshot_max_age_hours"] = self.screenshot_max_age_spin.value()

            # 主动对话设置
            config["enable_proactive_dialog"] = self.enable_proactive_check.isChecked()
            config["proactive_probability"] = (
                self.proactive_probability_slider.value() / 100.0
            )
            config["proactive_min_interval"] = self.proactive_min_interval_spin.value()
            config["proactive_max_interval"] = self.proactive_max_interval_spin.value()
            config["window_change_enabled"] = self.window_change_check.isChecked()
            config["window_change_probability"] = (
                self.window_change_probability_slider.value() / 100.0
            )
            config["scheduled_greetings_enabled"] = (
                self.scheduled_greetings_check.isChecked()
            )

            # 其他设置
            config["enable_tts"] = self.enable_tts_check.isChecked()
            config["auto_play_voice"] = self.auto_play_voice_check.isChecked()

            return config

        def _on_select_avatar(self):
            """选择头像图片"""
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择头像图片",
                "",
                "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)",
            )
            if file_path:
                self._set_avatar_preview(file_path)
                self.avatar_path_label.setText(file_path)

        def _on_clear_avatar(self):
            """清除头像"""
            self.avatar_preview.setPixmap(QPixmap())
            self.avatar_preview.setText("无头像")
            self.avatar_path_label.setText("未设置")

        def _set_avatar_preview(self, file_path: str):
            """设置头像预览"""
            if os.path.exists(file_path):
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        76,
                        76,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.avatar_preview.setPixmap(scaled)
                    self.avatar_preview.setText("")

        def _on_monitor_enabled_changed(self):
            """桌面监控启用状态改变"""
            enabled = self.enable_monitor_check.isChecked()
            self.monitor_interval_spin.setEnabled(enabled)
            self.max_screenshots_spin.setEnabled(enabled)
            self.screenshot_max_age_spin.setEnabled(enabled)

        def _on_proactive_enabled_changed(self):
            """主动对话启用状态改变"""
            enabled = self.enable_proactive_check.isChecked()
            self.proactive_probability_slider.setEnabled(enabled)
            self.proactive_min_interval_spin.setEnabled(enabled)
            self.proactive_max_interval_spin.setEnabled(enabled)
            self.window_change_check.setEnabled(enabled)
            self.window_change_probability_slider.setEnabled(enabled)
            self.scheduled_greetings_check.setEnabled(enabled)

        def _on_auto_start_changed(self, state: int):
            """开机自启动状态改变"""
            if sys.platform == "win32":
                try:
                    self._set_auto_start(state == Qt.CheckState.Checked.value)
                except Exception as e:
                    QMessageBox.warning(
                        self, "警告", f"设置开机自启动失败: {str(e)}"
                    )
                    # 回滚状态
                    self.auto_start_check.blockSignals(True)
                    self.auto_start_check.setChecked(not state)
                    self.auto_start_check.blockSignals(False)

        def _check_auto_start(self) -> bool:
            """检查是否已设置开机自启动"""
            if sys.platform != "win32":
                return False

            try:
                import winreg

                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0,
                    winreg.KEY_READ,
                )
                try:
                    winreg.QueryValueEx(key, "AstrBotDesktopAssistant")
                    return True
                except FileNotFoundError:
                    return False
                finally:
                    winreg.CloseKey(key)
            except Exception:
                return False

        def _set_auto_start(self, enable: bool):
            """设置开机自启动（Windows）"""
            if sys.platform != "win32":
                return

            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "AstrBotDesktopAssistant"

            try:
                if enable:
                    # 获取当前 Python 解释器路径
                    python_exe = sys.executable
                    # 获取 main.py 路径
                    main_script = os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..", "main.py")
                    )
                    command = f'"{python_exe}" "{main_script}"'

                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        key_path,
                        0,
                        winreg.KEY_SET_VALUE,
                    )
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
                    winreg.CloseKey(key)
                else:
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        key_path,
                        0,
                        winreg.KEY_SET_VALUE,
                    )
                    try:
                        winreg.DeleteValue(key, app_name)
                    except FileNotFoundError:
                        pass  # 值不存在，忽略
                    winreg.CloseKey(key)
            except Exception as e:
                raise RuntimeError(f"设置注册表失败: {e}")

        def _on_reset_defaults(self):
            """恢复默认设置"""
            reply = QMessageBox.question(
                self,
                "确认",
                "是否要恢复所有设置为默认值？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # 默认值
                defaults = {
                    "ball_size": 64,
                    "ball_opacity": 0.9,
                    "avatar_path": "",
                    "window_width": 400,
                    "window_height": 600,
                    "font_size": 14,
                    "enable_desktop_monitor": True,
                    "monitor_interval": 60,
                    "max_screenshots": 20,
                    "screenshot_max_age_hours": 24,
                    "enable_proactive_dialog": True,
                    "proactive_probability": 0.3,
                    "proactive_min_interval": 300,
                    "proactive_max_interval": 900,
                    "window_change_enabled": True,
                    "window_change_probability": 0.2,
                    "scheduled_greetings_enabled": True,
                    "enable_tts": True,
                    "auto_play_voice": False,
                }
                self.config = defaults
                self._load_config_to_ui()

        def _on_save(self):
            """保存设置"""
            # 验证设置
            min_interval = self.proactive_min_interval_spin.value()
            max_interval = self.proactive_max_interval_spin.value()

            if min_interval >= max_interval:
                QMessageBox.warning(
                    self,
                    "警告",
                    "主动对话的最小间隔必须小于最大间隔！",
                )
                return

            # 保存到配置
            new_config = self._save_ui_to_config()
            self.config = new_config

            # 发射信号
            self.settings_saved.emit(new_config)

            # 调用回调
            if self.on_settings_changed:
                self.on_settings_changed(new_config)

            # 关闭对话框
            self.accept()

        def get_config(self) -> dict:
            """获取当前配置"""
            return self.config.copy()


else:

    class SettingsWindow:
        """PySide6 不可用时的占位类"""

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "PySide6 is required for SettingsWindow. "
                "Please install it with: pip install PySide6"
            )