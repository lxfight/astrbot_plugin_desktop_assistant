"""
音频录制服务

提供语音录制和播放功能。
"""

from __future__ import annotations

import os
import time
import threading
from typing import Optional, Callable
from io import BytesIO

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

try:
    import soundfile as sf
    import numpy as np
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False


class AudioRecorderService:
    """音频录制服务"""
    
    def __init__(
        self,
        save_dir: str = "./temp/audio",
        sample_rate: int = 16000,
        channels: int = 1
    ):
        """
        初始化音频录制服务
        
        Args:
            save_dir: 音频保存目录
            sample_rate: 采样率
            channels: 声道数
        """
        self.save_dir = save_dir
        self.sample_rate = sample_rate
        self.channels = channels
        os.makedirs(save_dir, exist_ok=True)
        
        if not HAS_SOUNDDEVICE:
            raise ImportError("sounddevice 库未安装，请执行: pip install sounddevice")
        if not HAS_SOUNDFILE:
            raise ImportError("soundfile 库未安装，请执行: pip install soundfile")
            
        # 录制状态
        self._is_recording = False
        self._recorded_data: list = []
        self._record_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._record_start_time: Optional[float] = None
        
    @property
    def is_recording(self) -> bool:
        """是否正在录制"""
        return self._is_recording
        
    @property
    def recording_duration(self) -> float:
        """获取当前录制时长（秒）"""
        if self._record_start_time is None:
            return 0.0
        if self._is_recording:
            return time.time() - self._record_start_time
        return 0.0
        
    def start_recording(self) -> bool:
        """
        开始录制
        
        Returns:
            是否成功开始录制
        """
        if self._is_recording:
            return False
            
        self._is_recording = True
        self._recorded_data = []
        self._stop_event.clear()
        self._record_start_time = time.time()
        
        def record_callback(indata, frames, time_info, status):
            if status:
                print(f"录制状态: {status}")
            if not self._stop_event.is_set():
                self._recorded_data.append(indata.copy())
                
        def record_thread():
            try:
                with sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    callback=record_callback
                ):
                    while not self._stop_event.is_set():
                        sd.sleep(100)
            except Exception as e:
                print(f"录制错误: {e}")
            finally:
                self._is_recording = False
                
        self._record_thread = threading.Thread(target=record_thread, daemon=True)
        self._record_thread.start()
        return True
        
    def stop_recording(self, save_to_file: bool = True) -> Optional[str]:
        """
        停止录制
        
        Args:
            save_to_file: 是否保存到文件
            
        Returns:
            如果保存到文件，返回文件路径；否则返回 None
        """
        if not self._is_recording:
            return None
            
        self._stop_event.set()
        if self._record_thread:
            self._record_thread.join(timeout=1.0)
            
        self._is_recording = False
        duration = self.recording_duration
        self._record_start_time = None
        
        if not self._recorded_data:
            return None
            
        # 合并录制数据
        audio_data = np.concatenate(self._recorded_data, axis=0)
        
        if save_to_file:
            filename = f"recording_{int(time.time() * 1000)}.wav"
            filepath = os.path.join(self.save_dir, filename)
            sf.write(filepath, audio_data, self.sample_rate)
            return filepath
        
        return None
        
    def get_audio_duration(self, audio_path: str) -> float:
        """
        获取音频文件时长（秒）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            时长（秒）
        """
        try:
            info = sf.info(audio_path)
            return info.duration
        except Exception:
            return 0.0
            
    def get_recorded_data(self) -> Optional[np.ndarray]:
        """
        获取录制的音频数据
        
        Returns:
            numpy 数组格式的音频数据
        """
        if not self._recorded_data:
            return None
        return np.concatenate(self._recorded_data, axis=0)
        
    def save_to_file(
        self, 
        audio_data: np.ndarray, 
        filename: Optional[str] = None
    ) -> str:
        """
        保存音频数据到文件
        
        Args:
            audio_data: 音频数据
            filename: 文件名
            
        Returns:
            保存的文件路径
        """
        if filename is None:
            filename = f"audio_{int(time.time() * 1000)}.wav"
        filepath = os.path.join(self.save_dir, filename)
        sf.write(filepath, audio_data, self.sample_rate)
        return filepath
        
    def play_audio(self, audio_path: str, callback: Optional[Callable] = None):
        """
        播放音频文件
        
        Args:
            audio_path: 音频文件路径
            callback: 播放完成回调
        """
        def play_thread():
            try:
                data, samplerate = sf.read(audio_path)
                sd.play(data, samplerate)
                sd.wait()
                if callback:
                    callback()
            except Exception as e:
                print(f"播放音频失败: {e}")
                
        thread = threading.Thread(target=play_thread, daemon=True)
        thread.start()
        
    def stop_playback(self):
        """停止播放"""
        try:
            sd.stop()
        except Exception:
            pass
            
    @staticmethod
    def get_input_devices() -> list:
        """
        获取可用的输入设备列表
        
        Returns:
            输入设备列表
        """
        try:
            devices = sd.query_devices()
            return [
                {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
                for i, d in enumerate(devices)
                if d["max_input_channels"] > 0
            ]
        except Exception as e:
            print(f"获取输入设备失败: {e}")
            return []
            
    @staticmethod
    def get_output_devices() -> list:
        """
        获取可用的输出设备列表
        
        Returns:
            输出设备列表
        """
        try:
            devices = sd.query_devices()
            return [
                {"index": i, "name": d["name"], "channels": d["max_output_channels"]}
                for i, d in enumerate(devices)
                if d["max_output_channels"] > 0
            ]
        except Exception as e:
            print(f"获取输出设备失败: {e}")
            return []