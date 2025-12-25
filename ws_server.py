"""
独立 WebSocket 服务器模块

使用 websockets 库创建独立的 WebSocket 服务器，监听端口 6190。
这个方案不依赖 AstrBot 主应用，避免了框架兼容性问题。

桌面客户端连接地址: ws://服务器IP:6190
"""

import asyncio
import json
import traceback
from typing import Optional, Callable, Any, Dict, Set
from urllib.parse import parse_qs, urlparse

try:
    import websockets
    from websockets.server import serve, WebSocketServerProtocol
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = None

from astrbot.api import logger


class StandaloneWebSocketServer:
    """
    独立 WebSocket 服务器
    
    使用 websockets 库在指定端口运行，不依赖 AstrBot 主应用。
    支持客户端认证、心跳检测、消息分发等功能。
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 6190,
        on_client_connect: Optional[Callable[[str], Any]] = None,
        on_client_disconnect: Optional[Callable[[str], Any]] = None,
        on_message: Optional[Callable[[str, dict], Any]] = None,
    ):
        """
        初始化 WebSocket 服务器
        
        Args:
            host: 监听地址，默认 0.0.0.0（所有网卡）
            port: 监听端口，默认 6190
            on_client_connect: 客户端连接回调
            on_client_disconnect: 客户端断开回调  
            on_message: 消息接收回调
        """
        self.host = host
        self.port = port
        self.on_client_connect = on_client_connect
        self.on_client_disconnect = on_client_disconnect
        self.on_message = on_message
        
        # 活跃连接: session_id -> websocket
        self.connections: Dict[str, WebSocketServerProtocol] = {}
        
        # 服务器状态
        self._server = None
        self._running = False
        self._server_task: Optional[asyncio.Task] = None
        
    @property
    def is_running(self) -> bool:
        """服务器是否正在运行"""
        return self._running and self._server is not None
    
    def get_connected_client_ids(self) -> list:
        """获取所有已连接客户端的 session_id"""
        return list(self.connections.keys())
    
    def get_active_clients_count(self) -> int:
        """获取活跃客户端数量"""
        return len(self.connections)
    
    async def start(self):
        """启动 WebSocket 服务器"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("❌ websockets 库未安装，无法启动 WebSocket 服务器")
            logger.error("   请运行: pip install websockets>=12.0")
            return False
        
        if self._running:
            logger.warning("WebSocket 服务器已在运行中")
            return True
        
        try:
            # 创建服务器
            self._server = await serve(
                self._handle_connection,
                self.host,
                self.port,
                ping_interval=30,  # 心跳间隔 30 秒
                ping_timeout=10,   # 心跳超时 10 秒
            )
            
            self._running = True
            
            logger.info("=" * 60)
            logger.info("✅ WebSocket 服务器启动成功！")
            logger.info(f"   监听地址: {self.host}:{self.port}")
            logger.info(f"   桌面客户端连接地址: ws://服务器IP:{self.port}")
            logger.info("=" * 60)
            
            return True
            
        except OSError as e:
            if "address already in use" in str(e).lower() or e.errno == 10048:
                logger.error(f"❌ 端口 {self.port} 已被占用！")
                logger.error("   请检查是否有其他程序占用该端口，或修改配置使用其他端口")
            else:
                logger.error(f"❌ WebSocket 服务器启动失败: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ WebSocket 服务器启动失败: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def stop(self):
        """停止 WebSocket 服务器"""
        if not self._running:
            return
        
        self._running = False
        
        # 关闭所有连接
        for session_id, ws in list(self.connections.items()):
            try:
                await ws.close(1001, "Server shutting down")
            except Exception:
                pass
        self.connections.clear()
        
        # 关闭服务器
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        
        logger.info("WebSocket 服务器已停止")
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol):
        """
        处理 WebSocket 连接
        
        支持两种连接方式：
        1. ws://服务器IP:6190/ws/client?session_id=xxx&token=xxx (标准路径)
        2. ws://服务器IP:6190?session_id=xxx&token=xxx (根路径兼容)
        """
        # 解析 URL 路径和参数
        full_path = websocket.path if hasattr(websocket, 'path') else "/"
        
        # 分离路径和查询参数
        if "?" in full_path:
            path_part, query_string = full_path.split("?", 1)
        else:
            path_part = full_path
            query_string = ""
        
        params = parse_qs(query_string)
        
        # 验证路径（支持 /ws/client 和 / 两种路径）
        valid_paths = ["/ws/client", "/", ""]
        if path_part not in valid_paths:
            logger.warning(f"WebSocket 连接拒绝: 无效路径 '{path_part}'，支持的路径: {valid_paths}")
            await websocket.close(1008, f"Invalid path: {path_part}")
            return
        
        session_id = params.get("session_id", [None])[0]
        token = params.get("token", [None])[0]
        
        logger.info(f"收到 WebSocket 连接请求: path={path_part}, session_id={session_id}, token={'*' * 6 if token else 'None'}")
        
        # 验证参数
        if not session_id or not token:
            logger.warning("WebSocket 连接拒绝: 缺少 session_id 或 token")
            await websocket.close(1008, "Missing session_id or token")
            return
        
        # TODO: 验证 token 有效性（当前信任本地连接）
        
        # 记录连接
        self.connections[session_id] = websocket
        logger.info(f"✅ 客户端已连接: session_id={session_id}")
        
        # 触发连接回调
        if self.on_client_connect:
            try:
                result = self.on_client_connect(session_id)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"连接回调执行失败: {e}")
        
        try:
            # 消息循环
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(session_id, websocket, data)
                except json.JSONDecodeError:
                    logger.warning(f"收到无效 JSON 消息: {message[:100]}...")
                except Exception as e:
                    logger.error(f"处理消息失败: {e}")
                    logger.error(traceback.format_exc())
                    
        except ConnectionClosed as e:
            logger.info(f"客户端断开连接: session_id={session_id}, code={e.code}")
        except Exception as e:
            logger.error(f"WebSocket 连接错误: {e}")
        finally:
            # 清理连接
            self.connections.pop(session_id, None)
            logger.info(f"客户端已移除: session_id={session_id}")
            
            # 触发断开回调
            if self.on_client_disconnect:
                try:
                    result = self.on_client_disconnect(session_id)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"断开回调执行失败: {e}")
    
    async def _handle_message(
        self,
        session_id: str,
        websocket: WebSocketServerProtocol,
        data: dict
    ):
        """处理客户端消息"""
        msg_type = data.get("type", "")
        
        # 心跳消息
        if msg_type == "heartbeat":
            await self._send_json(websocket, {"type": "heartbeat_ack"})
            return
        
        # 触发消息回调
        if self.on_message:
            try:
                result = self.on_message(session_id, data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"消息回调执行失败: {e}")
    
    async def send_to_client(self, session_id: str, data: dict) -> bool:
        """
        发送消息给指定客户端
        
        Args:
            session_id: 客户端 session_id
            data: 要发送的数据（字典）
            
        Returns:
            是否发送成功
        """
        websocket = self.connections.get(session_id)
        if not websocket:
            logger.warning(f"发送失败: 客户端未连接 session_id={session_id}")
            return False
        
        return await self._send_json(websocket, data)
    
    async def broadcast(self, data: dict) -> int:
        """
        广播消息给所有客户端
        
        Args:
            data: 要发送的数据（字典）
            
        Returns:
            成功发送的客户端数量
        """
        success_count = 0
        for session_id, websocket in list(self.connections.items()):
            if await self._send_json(websocket, data):
                success_count += 1
            else:
                # 发送失败，移除连接
                self.connections.pop(session_id, None)
        return success_count
    
    async def _send_json(self, websocket: WebSocketServerProtocol, data: dict) -> bool:
        """发送 JSON 数据"""
        try:
            await websocket.send(json.dumps(data, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False