import uuid

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocket

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms = []

ws_clients = []


class Link:
    def __init__(self, url):
        self.url = url
        self.id = str(uuid.uuid4())

    def json(self):
        return {
            "id": self.id,
            "url": self.url
        }


class Room:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.links = []
        self.current_link = 0
        self.current_time = 0
        self.messages = []
        self.playing = False

    def add_link(self, link):
        self.links.append(Link(link))

    def get_current_link(self):
        if len(self.links) == 0:
            return ''
        return self.links[self.current_link].url

    def json(self):
        return {
            "id": self.id,
            "links": [link.json() for link in self.links],
            "current_link": self.get_current_link(),
            "current_time": self.current_time,
            "messages": self.messages,
            "playing": self.playing
        }


class Client:
    def __init__(self, websocket):
        self.websocket = websocket
        self.id = str(uuid.uuid4())
        self.room = None

    async def send(self, data):
        await self.websocket.send_json(data)


@app.get("/create_room")
async def root() -> dict:
    room = Room()
    rooms.append(room)
    return {"id": room.id}


async def send_to_room(room, data):
    for client in ws_clients:
        if client.room == room:
            await client.send(data)


@app.websocket("/ws/{room_id}")
@app.websocket("/ws/{room_id}/")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    client = Client(websocket)
    try:
        await websocket.accept()
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
            await send_to_room(client.room, {"status": "ok", "data": client.room.json()})
            data = await websocket.receive_json()
            print(data)
            match data['type']:
                case "get_room":
                    client.room.playing = False
                case "message":
                    client.room.messages.append(data["message"])
                case "refresh":
                    client.room.playing = False
                case "play_link":
                    url = data["url"]
                    if url in [link.url for link in client.room.links]:
                        client.room.current_link = [link.url for link in client.room.links].index(url)
                        client.room.current_time = 0
                        client.room.playing = False
                case "add_link":
                    client.room.add_link(data["url"])
                case "delete_link":
                    client.room.links = [link for link in client.room.links if link.id != data['id']]
                case "play":
                    client.room.playing = True
                case "pause":
                    client.room.current_time = data['time']
                    client.room.playing = False
                case "seek":
                    client.room.current_time = data['time']
                    # client.room.playing = False
            await send_to_room(client.room, {"status": "ok", "data": client.room.json()})
    except Exception as e:
        print(e)
        ws_clients.remove(client)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
