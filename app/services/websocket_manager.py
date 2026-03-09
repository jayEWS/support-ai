"""
WebSocket connection manager for real-time chat.
Handles broadcasting messages, typing indicators, and presence updates.
"""
import json
from typing import Dict, Set
from fastapi import WebSocket
from app.core.logging import logger

class ConnectionManager:
    def __init__(self):
        # Map of session_id -> set of active WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Map of session_id -> {agent_id, customer_id} for tracking participants
        self.session_participants: Dict[int, dict] = {}
        # Map of user_id -> typing flag (for tracking who's typing)
        self.typing_users: Dict[str, dict] = {}
        self.redis_service = None

    def set_redis(self, redis_service):
        """Enable distributed broadcasting via Redis."""
        self.redis_service = redis_service

    async def _handle_redis_message(self, data: dict):
        """Handle broadast received from Redis."""
        session_id = data.get("session_id")
        msg_payload = data.get("payload")
        if session_id and msg_payload:
            await self._local_broadcast(int(session_id), msg_payload)

    async def connect(self, session_id: int, user_id: str, user_type: str, websocket: WebSocket):
        """Register a new WebSocket connection for a chat session."""
        await websocket.accept()
        
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
            self.session_participants[session_id] = {}
        
        self.active_connections[session_id].add(websocket)
        
        # Track participant
        if user_type == "agent":
            self.session_participants[session_id]["agent_id"] = user_id
        else:
            self.session_participants[session_id]["customer_id"] = user_id
        
        logger.info(f"User {user_id} ({user_type}) connected to session {session_id}")
        
        # Broadcast user joined event
        await self.broadcast(session_id, {
            "event": "user_joined",
            "user_id": user_id,
            "user_type": user_type,
            "timestamp": None
        }, exclude_websocket=None)

    def disconnect(self, session_id: int, websocket: WebSocket):
        """Unregister a WebSocket connection."""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
                if session_id in self.session_participants:
                    del self.session_participants[session_id]
        
        logger.info(f"Connection disconnected from session {session_id}")

    async def broadcast(self, session_id: int, data: dict, exclude_websocket: WebSocket = None):
        """Broadcast a message to all users in a session (Distributed)."""
        # 1. Local broadcast
        await self._local_broadcast(session_id, data, exclude_websocket)
        
        # 2. Redis broadcast to other instances
        if self.redis_service and self.redis_service.enabled:
            await self.redis_service.publish("ws_broadcast", {
                "type": "connection_manager",
                "session_id": session_id,
                "payload": data
            })

    async def _local_broadcast(self, session_id: int, data: dict, exclude_websocket: WebSocket = None):
        """Helper for local-only broadcast."""
        if session_id not in self.active_connections:
            return
        
        message = json.dumps(data)
        dead_connections = []
        
        for connection in self.active_connections[session_id]:
            if exclude_websocket and connection == exclude_websocket:
                continue
            
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to connection: {e}")
                dead_connections.append(connection)
        
        # Clean up dead connections
        for conn in dead_connections:
            self.active_connections[session_id].discard(conn)

    async def send_to_user(self, session_id: int, user_id: str, data: dict):
        """Send a message to a specific user in a session."""
        if session_id not in self.active_connections:
            return
        
        message = json.dumps(data)
        
        # Find and send to user (rough match by checking their connection type)
        # In production, you'd track user_id -> WebSocket mapping more explicitly
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")

    async def broadcast_typing(self, session_id: int, user_id: str, user_name: str):
        """Broadcast that a user is typing."""
        self.typing_users[user_id] = {"session_id": session_id, "name": user_name}
        
        await self.broadcast(session_id, {
            "event": "typing_start",
            "user_id": user_id,
            "user_name": user_name,
            "timestamp": None
        })

    async def broadcast_stop_typing(self, session_id: int, user_id: str):
        """Broadcast that a user stopped typing."""
        if user_id in self.typing_users:
            del self.typing_users[user_id]
        
        await self.broadcast(session_id, {
            "event": "typing_stop",
            "user_id": user_id,
            "timestamp": None
        })

    async def broadcast_presence(self, agent_id: str, status: str, active_chat_count: int):
        """Broadcast agent presence/status update to all sessions."""
        data = {
            "event": "presence_update",
            "agent_id": agent_id,
            "status": status,
            "active_chat_count": active_chat_count,
            "timestamp": None
        }
        
        # Broadcast to all active sessions (agents see presence)
        for session_id in self.active_connections.keys():
            await self.broadcast(session_id, data)

    async def broadcast_message_read(self, session_id: int, message_id: int, read_at: str):
        """Broadcast read receipt."""
        await self.broadcast(session_id, {
            "event": "message_read",
            "message_id": message_id,
            "read_at": read_at,
            "timestamp": None
        })

    async def broadcast_session_closed(self, session_id: int):
        """Notify all participants that the session has been closed."""
        await self.broadcast(session_id, {
            "event": "session_closed",
            "session_id": session_id,
            "timestamp": None
        })

    def get_active_users_in_session(self, session_id: int):
        """Get list of active users in a session."""
        if session_id not in self.session_participants:
            return []
        
        return self.session_participants[session_id]

    def get_session_connection_count(self, session_id: int):
        """Get number of active connections in a session."""
        return len(self.active_connections.get(session_id, set()))


# Global manager instance
manager = ConnectionManager()


class PortalConnectionManager:
    """WebSocket manager for portal user connections (user_id based).
    Used to push agent replies and events to customer portal in real-time."""

    def __init__(self):
        # Map of user_id -> set of WebSocket connections
        self.connections: Dict[str, Set[WebSocket]] = {}
        # Map of user_id -> set of admin WebSocket connections watching this chat
        self.admin_watchers: Dict[str, Set[WebSocket]] = {}
        self.redis_service = None

    def set_redis(self, redis_service):
        """Enable distributed broadcasting via Redis."""
        self.redis_service = redis_service

    async def _handle_redis_message(self, data: dict):
        """Handle broadcast received from Redis."""
        msg_type = data.get("msg_type")
        user_id = data.get("user_id")
        payload = data.get("payload")
        
        if msg_type == "to_user":
            await self._local_send_to_user(user_id, payload)
        elif msg_type == "to_admins":
            await self._local_send_to_admins(user_id, payload)
        elif msg_type == "to_all_admins":
            await self._local_broadcast_to_all_admins(payload)

    async def connect_user(self, user_id: str, websocket: WebSocket):
        """Register a customer portal WebSocket connection."""
        await websocket.accept()
        if user_id not in self.connections:
            self.connections[user_id] = set()
        self.connections[user_id].add(websocket)
        logger.info(f"Portal user {user_id} connected via WebSocket")

    async def connect_admin(self, user_id: str, websocket: WebSocket):
        """Register an admin watching a customer's chat."""
        await websocket.accept()
        if user_id not in self.admin_watchers:
            self.admin_watchers[user_id] = set()
        self.admin_watchers[user_id].add(websocket)
        logger.info(f"Admin connected to watch portal user {user_id}")

    def disconnect_user(self, user_id: str, websocket: WebSocket):
        """Remove a customer portal connection."""
        if user_id in self.connections:
            self.connections[user_id].discard(websocket)
            if not self.connections[user_id]:
                del self.connections[user_id]
        logger.info(f"Portal user {user_id} disconnected")

    def disconnect_admin(self, user_id: str, websocket: WebSocket):
        """Remove an admin watcher connection."""
        if user_id in self.admin_watchers:
            self.admin_watchers[user_id].discard(websocket)
            if not self.admin_watchers[user_id]:
                del self.admin_watchers[user_id]

    async def send_to_user(self, user_id: str, data: dict):
        """Send a message to a specific portal user (Distributed)."""
        await self._local_send_to_user(user_id, data)
        if self.redis_service and self.redis_service.enabled:
            await self.redis_service.publish("ws_portal_broadcast", {
                "msg_type": "to_user",
                "user_id": user_id,
                "payload": data
            })

    async def _local_send_to_user(self, user_id: str, data: dict):
        if user_id not in self.connections:
            return
        message = json.dumps(data)
        dead = []
        for ws in self.connections[user_id]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections[user_id].discard(ws)

    async def send_to_admins(self, user_id: str, data: dict):
        """Send a message to all admins watching a user's chat (Distributed)."""
        await self._local_send_to_admins(user_id, data)
        if self.redis_service and self.redis_service.enabled:
            await self.redis_service.publish("ws_portal_broadcast", {
                "msg_type": "to_admins",
                "user_id": user_id,
                "payload": data
            })

    async def _local_send_to_admins(self, user_id: str, data: dict):
        if user_id not in self.admin_watchers:
            return
        message = json.dumps(data)
        dead = []
        for ws in self.admin_watchers[user_id]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.admin_watchers[user_id].discard(ws)

    async def broadcast_to_all_admins(self, data: dict):
        """Send a message to ALL connected admin watchers (Distributed)."""
        await self._local_broadcast_to_all_admins(data)
        if self.redis_service and self.redis_service.enabled:
            await self.redis_service.publish("ws_portal_broadcast", {
                "msg_type": "to_all_admins",
                "payload": data
            })

    async def _local_broadcast_to_all_admins(self, data: dict):
        message = json.dumps(data)
        for user_id in list(self.admin_watchers.keys()):
            dead = []
            for ws in self.admin_watchers[user_id]:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.admin_watchers[user_id].discard(ws)

    def get_online_users(self) -> list:
        """Get list of user_ids currently connected via portal WebSocket."""
        return list(self.connections.keys())

    def is_user_online(self, user_id: str) -> bool:
        """Check if a user is currently connected."""
        return user_id in self.connections and len(self.connections[user_id]) > 0


# Global portal manager instance
portal_manager = PortalConnectionManager()
