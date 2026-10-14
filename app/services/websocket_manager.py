
import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self.queue_connections = defaultdict(set)
        self.user_connections = defaultdict(set)
        self.lock = asyncio.Lock()

    async def connect_queue(self, doctor_id: int, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.queue_connections[doctor_id].add(websocket)

    async def connect_user(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.user_connections[user_id].add(websocket)

    async def disconnect_queue(self, doctor_id: int, websocket: WebSocket):
        async with self.lock:
            self.queue_connections[doctor_id].discard(websocket)
            if not self.queue_connections[doctor_id]:
                self.queue_connections.pop(doctor_id, None)

    async def disconnect_user(self, user_id: int, websocket: WebSocket):
        async with self.lock:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                self.user_connections.pop(user_id, None)

    async def broadcast_queue(self, doctor_id: int, message: dict):
        async with self.lock:
            connections = list(self.queue_connections.get(doctor_id, set()))

        disconnected = []

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            await self.disconnect_queue(doctor_id, websocket)

    async def notify_user(self, user_id: int, message: dict):
        async with self.lock:
            connections = list(self.user_connections.get(user_id, set()))

        disconnected = []

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            await self.disconnect_user(user_id, websocket)


manager = WebSocketManager()
