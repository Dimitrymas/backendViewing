import uuid

from fastapi import FastAPI
from starlette.websockets import WebSocket

app = FastAPI()

rooms = []

ws_clients = []


class Link:
    def __init__(self, url):
        self.url = url
        self.id = uuid.uuid4()

    def json(self):
        return {
            "id": self.id,
            "url": self.url
        }


class Room:
    def __init__(self):
        self.id = uuid.uuid4()
        self.links = []
        self.current_link = 0
        self.current_time = 0
        self.messages = []
        self.playing = False

    def add_link(self, link):
        self.links.append(Link(link))

    def next_link(self):
        self.current_link += 1
        self.current_time = 0
        self.playing = False
        if self.current_link >= len(self.links):
            self.current_link = 0

    def get_current_link(self):
        return self.links[self.current_link]

    def json(self):
        return {
            "id": self.id,
            "links": [link.url for link in self.links],
            "current_link": self.get_current_link().json(),
            "current_time": self.current_time,
            "messages": self.messages,
            "playing": self.playing
        }


class Client:
    def __init__(self, websocket):
        self.websocket = websocket
        self.id = uuid.uuid4()
        self.room = None

    async def send(self, data):
        await self.websocket.send_json(data)


@app.get("/create_room")
async def root() -> dict:
    room = Room()
    rooms.append(room)
    return {"status": "ok", "room_id": room.id}


@app.get("/get_rooms")
async def get_rooms() -> dict:
    return [room.json() for room in rooms]


async def send_to_room(room, data):
    for client in ws_clients:
        if client.room == room:
            await client.send(data)


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    client = Client(websocket)
    ws_clients.append(client)
    for room in rooms:
        if room.id == room_id:
            client.room = room
            break
    while True:
        if client.room is None:
            await client.send({"status": "error", "message": "Room not found"})
            await websocket.close()
            return

        data = await websocket.receive_json()
        match data['type']:
            case "get_room":
                client.room.playing = False
            case "message":
                client.room.messages.append(data["message"])
            case "refresh":
                client.room.playing = False
            case "next":
                client.room.next_link()
            case "add_link":
                client.room.add_link(data["link"])
            case "remove_link":
                client.room.links = [link for link in client.room.links if link.url != data['link']]
            case "play":
                client.room.playing = True
            case "pause":
                client.room.playing = False
            case "seek":
                client.room.current_time = data['time']
                client.room.playing = False
        await send_to_room(client.room, client.room.json())

