#!/usr/bin/env python3
import json

from aiohttp import web, WSMsgType, WSMessage


class WSChat:
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.conns: dict[str, web.WebSocketResponse] = {}

    async def main_page(self, request):
        return web.FileResponse('./index.html')

    async def websocket_handler(self, request: web.Request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        handler = WsMessageHandler(ws, self)
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await handler.handle(msg)
            elif msg.type == WSMsgType.ERROR:
                print('ws connection closed with exception %s' %
                      ws.exception())

        await handler.user_leave()
        print('websocket connection closed')
        return ws

    def run(self):
        app = web.Application()

        app.router.add_get('/', self.main_page)

        app.router.add_get('/chat', self.websocket_handler)

        web.run_app(app, host=self.host, port=self.port)


class WsMessageHandler:
    def __init__(self, ws: web.WebSocketResponse, chat: WSChat):
        self.ws = ws
        self.chat = chat
        self.user_id = None

    async def handle(self, msg: WSMessage):
        if msg.data == 'ping':
            await self.ws.send_str('pong')
            return

        msg_json = msg.json()
        match msg_json['mtype']:
            case 'INIT':
                await self.user_enter(msg_json['id'])
            case 'TEXT':
                await self.send_text(msg_json['id'], msg_json['to'], msg_json['text'])

    async def send_text(self, id, to, text):
        if not to:
            await self.broadcast_with_text(id, text)
            return

        if to not in self.chat.conns:
            return

        await self.direct_message(id, to, text)

    async def direct_message(self, id, to, text):
        message = {'mtype': 'DM', 'id': id, 'text': text}
        await self.chat.conns[to].send_json(message)

    async def broadcast_with_text(self, id, text):
        message = {'mtype': 'MSG', 'id': id, 'text': text}
        await self.broadcast_message(id, message)

    async def user_enter(self, id):
        self.user_id = id
        self.chat.conns[id] = self.ws
        await self.service_message('USER_ENTER', id)

    async def user_leave(self):
        if self.user_id in self.chat.conns:
            self.chat.conns.pop(self.user_id)
            await self.service_message('USER_LEAVE', self.user_id)

    async def service_message(self, type, id):
        message = {'mtype': type, 'id': id}
        await self.broadcast_message(id, message)

    async def broadcast_message(self, sender_id, message):
        for client, ws in self.chat.conns.items():
            if client != sender_id:
                await ws.send_json(message)


if __name__ == '__main__':
    WSChat().run()
