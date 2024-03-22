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
        self.is_playing = False

    def json(self):
        return {
            "id": self.id,
            "url": self.url,
            "is_playing": self.is_playing
        }


class Room:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.links = []
        self.current_link = 0
        self.current_time = 0
        self.messages = []
        self.playing = False

    def __stop_links(self):
        for i in self.links:
            i.is_playing = False

    def add_link(self, link):
        self.__stop_links()
        self.links.append(Link(link))
        if self.current_link == 0:
            self.links[0].is_playing = True

    def next_link(self):
        self.__stop_links()
        self.playing = False
        if self.current_link + 1 < len(self.links):
            self.current_link += 1
            self.current_time = 0
            self.links[self.current_link].is_playing = True

    def get_current_link(self):
        if len(self.links) == 0:
            return ''
        return self.links[self.current_link].url

    def choice_link(self, link_id):
        self.__stop_links()
        for i, link in enumerate(self.links):
            if link.id == link_id:
                self.current_link = i
                self.current_time = 0
                self.playing = False
                link.is_playing = True

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
                    client.room.choice_link(data["id"])
                case "add_link":
                    client.room.add_link(data["url"])
                case "end":
                    client.room.next_link()
                case "delete_link":
                    link = [link for link in client.room.links if link.id == data['id']][0]
                    link_index = client.room.links.index(link)
                    client.room.links.remove(link)
                    if link.is_playing:
                        if link_index + 1 < len(client.room.links):
                            client.room.next_link()
                        else:
                            client.room.playing = False
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
