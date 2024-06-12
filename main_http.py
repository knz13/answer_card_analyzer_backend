import asyncio
from contextlib import asynccontextmanager
from typing import Dict, List
import cv2
import numpy as np
from PIL import Image
import os
from base64 import b64decode, b64encode
from find_circles import find_circles, find_circles_cv2, show_image
from read_to_images import read_to_images
from utils import Utils
from websocket_types import WebsocketMessageCommand, WebsocketMessageStatus
import json
import io
from hypercorn.config import Config
from hypercorn.asyncio import serve
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket,WebSocketDisconnect,WebSocketClose
from queue import SimpleQueue
import random

from fastapi.middleware.cors import CORSMiddleware



class WebsocketInternalClient:
    def __init__(self,websocket: WebSocket, id: str):
        self.websocket = websocket
        self.id = id
        self.jobs = 0
        self.messages_per_task: Dict[str,SimpleQueue] = {}
        self.on_progress_per_task = {}
        self.last_pong = asyncio.get_event_loop().time()
    
    async def send_ping(self):
        
        await self.websocket.send_text(json.dumps({"command": WebsocketMessageCommand.PING,"data": None}))
    
    def received_pong(self):
        Utils.log_info(f"Received pong from: {self.id}")
        self.last_pong = asyncio.get_event_loop().time()
    
class WebsocketInternalClientJob:
    def __init__(self,command: WebsocketMessageCommand, data: Dict,files: Dict[str,bytes] = {}):
        self.command = command
        self.data = data
        self.files = files
    

def image_as_encoded(image):
    byte_arr = io.BytesIO()
    image.save(byte_arr, format='PNG') # convert the PIL image to byte array
    encoded_img = b64encode(byte_arr.getvalue()).decode('utf-8') # encode as base64
    return encoded_img

async def ping_internal_clients():
    Utils.log_info("Starting ping_internal_clients")
    while True:
        try:
            for client_id, client in list(internal_clients.items()):
                if client.last_pong - asyncio.get_event_loop().time() > 120:
                    Utils.log_info(f"Internal client {client_id} disconnected due to inactivity.")
                    await handle_internal_client_disconnect(client_id)
                    continue
                try:
                    Utils.log_info(f"Sending ping to client {client_id} at {asyncio.get_event_loop().time()}.")
                    await client.send_ping()
                except Exception as e:
                    Utils.log_error(f"Failed to send ping to client {client_id}: {e}")
        except Exception as e:
            Utils.log_error(f"In function ping_internal_clients: {e}")
        await asyncio.sleep(20)  # Ping every minute


@asynccontextmanager
async def lifespanFunction(app: FastAPI):
    asyncio.create_task(ping_internal_clients())

    yield

app = FastAPI(lifespan=lifespanFunction)

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


clients: Dict[str,WebSocket] = {}  # Dictionary to track WebSocket sessions by ID
internal_clients: Dict[str,WebsocketInternalClient] = {}  # Dictionary to track WebSocket sessions by ID

async def send_progress(websocket: WebSocket, message, task_id):
    await websocket.send_text(json.dumps({"status": WebsocketMessageStatus.PROGRESS,'data': {
        'task_id': task_id,
        'message': message
    }}))

CHUNK_SIZE = 1024 * 200 # 200kb

async def send_bytes_in_chunks(websocket: WebSocket, task_id: str,file_data: bytes,file_id: str):
    #print(f"Sending {len(file_data)} bytes in chunks.")
    for i in range(0, len(file_data), CHUNK_SIZE):
        #print(f"Sending chunk {i}.")
        chunk = file_data[i:i+CHUNK_SIZE]

        #print(f"Chunk {i} size: {len(chunk)}")
        status = WebsocketMessageStatus.SENDING_CHUNK
        if  i + CHUNK_SIZE >= len(file_data):
            status = WebsocketMessageStatus.FINAL_CHUNK
        await websocket.send_text(json.dumps({"status": status,'data': {
            'chunk': b64encode(chunk).decode('utf-8'),
            "task_id": task_id,
            "file_id": file_id
        }}))

async def send_job_to_internal_client(client_id: str, job: WebsocketInternalClientJob):
    Utils.log_info(f"Sending job to internal client {client_id}")

    socket = internal_clients[client_id]

    
    socket.messages_per_task[job.data["task_id"]] = SimpleQueue()

    internal_clients[client_id].jobs += 1

    await socket.websocket.send_text(json.dumps({
        "command": job.command,
        "data": job.data
    }))
    
    for file_id in job.files:
        await send_bytes_in_chunks(socket.websocket,job.data["task_id"],job.files[file_id],file_id)
    
    

@app.post("/read_to_images")
async def read_to_images_route(file: UploadFile = File(...), task_id: str = Form(...), socket_id: str = Form(...)):
    Utils.log_info("Received request to read PDF to images.")
    Utils.log_info(f"Received file: {file.filename}")

    Utils.log_info(f"Socket ID: {socket_id}, websocket: {clients[socket_id]}")

    if len(internal_clients) == 0:
        Utils.log_info("No internal clients connected.")
        raise HTTPException(status_code=404, detail="No internal clients connected.")
    
    chosen_internal_client = random.choice(list(internal_clients.keys()))
    
    file_id = random.randbytes(16).hex()

    job = WebsocketInternalClientJob(WebsocketMessageCommand.READ_TO_IMAGES, {
        "socket_id": socket_id,
        "task_id": task_id,
        "filename": file.filename,
    }, {file_id: await file.read()})
    
    response = await handle_internal_client_task(internal_clients[chosen_internal_client], job,on_progress=lambda x: send_progress(clients[socket_id], x, task_id) if socket_id in clients else None)

    if type(response) == JSONResponse:
        Utils.log_error(f"Error occurred: {response}")
        return response
    else:

        return JSONResponse(content={"status": WebsocketMessageStatus.COMPLETED_TASK, "data": {
            **response["data"],
            "files": response["files"]
        }})

    try:
        if socket_id in clients:
            await send_progress(clients[socket_id], "Starting to read PDF to images.", task_id)
        images = await read_to_images(file, task_id, on_progress=lambda x: send_progress(clients[socket_id], x, task_id) if socket_id in clients else None) 
        if socket_id in clients:
            await send_progress(clients[socket_id], "Completed reading PDF to images.", task_id)
        
        for image in images["images"]:
            images["images"][image] = image_as_encoded(images["images"][image])

        return JSONResponse(content={"status": WebsocketMessageStatus.COMPLETED_TASK, "data": images})
    except Exception as e:
        print(f"An error occurred: {e.__traceback__}")
        return JSONResponse(content={"status": WebsocketMessageStatus.ERROR, "error": str(e)}), 500
    



@app.post('/find_circles')
async def find_circles_route(file: UploadFile = File(...), task_id: str = Form(...), socket_id: str = Form(...), data: str = Form(...)):
    Utils.log_info("Received request to find circles.")
    Utils.log_info(f"Received file: {file.filename}")
    
    if len(internal_clients) == 0:
        Utils.log_info("No internal clients connected.")
        raise HTTPException(status_code=404, detail="No internal clients connected.")

    chosen_internal_client = random.choice(list(internal_clients.keys()))
    
    file_id = random.randbytes(16).hex()

    job = WebsocketInternalClientJob(WebsocketMessageCommand.FIND_CIRCLES, {
        "socket_id": socket_id,
        "task_id": task_id,
        "filename": file.filename,
        **json.loads(data)
    }, {file_id: await file.read()})
    
    response = await handle_internal_client_task(internal_clients[chosen_internal_client], job,on_progress=lambda x: send_progress(clients[socket_id], x, task_id) if socket_id in clients else None)

    if type(response) == JSONResponse:
        return response
    else:
        return JSONResponse(content={"status": WebsocketMessageStatus.COMPLETED_TASK, "data": {
            **response["data"],
            "files": response["files"]
        }})


async def handle_internal_client_task(internal_client: WebsocketInternalClient, job: WebsocketInternalClientJob, on_progress=None):
    job_data = {
        "file_ids": list(job.files.keys()),
        **job.data
    }

    if on_progress is not None:
        await on_progress("Sending job to processing server...")

    if len(internal_clients) == 0:
        Utils.log_info("No internal clients connected.")
        raise HTTPException(status_code=404, detail="No internal clients connected.")
    
    internal_client.on_progress_per_task[job_data["task_id"]] = on_progress

    await send_job_to_internal_client(internal_client.id, WebsocketInternalClientJob(job.command, job_data, job.files))
    chunks_per_file = {}
    files_received = {}


    Utils.log_info(f"Received files: {len(job.files)}")
    Utils.log_info(f"Socket ID: {internal_client.id}, websocket: {internal_client.websocket}")
    if job.command == WebsocketMessageCommand.READ_TO_IMAGES:
        Utils.log_info("Received request to read PDF to images.")

    elif job.command == WebsocketMessageCommand.FIND_CIRCLES:
        Utils.log_info("Received request to find circles.")

    try:
        while True:

            
            if internal_client.messages_per_task[job_data["task_id"]].empty():
                await asyncio.sleep(0.1)
                continue

            message = internal_client.messages_per_task[job_data["task_id"]].get()
            Utils.log_info(f'Internal message on task "{job.data["task_id"]}": {message["status"]}')

            if message["status"] == WebsocketMessageStatus.ERROR:
                internal_client.jobs -= 1
                del internal_client.on_progress_per_task[job_data["task_id"]]
                return JSONResponse(content={"status": WebsocketMessageStatus.ERROR, "error": message["data"]})
            elif message["status"] == WebsocketMessageStatus.COMPLETED_TASK:
                internal_client.jobs -= 1
                del internal_client.on_progress_per_task[job_data["task_id"]]
                return {
                    "data": message["data"],
                    "files": files_received
                }
            elif message["status"] == WebsocketMessageStatus.SENDING_CHUNK:
                if message["data"]["file_id"] not in chunks_per_file:
                    chunks_per_file[message["data"]["file_id"]] = bytearray()
                chunks_per_file[message["data"]["file_id"]] += bytearray(b64decode(message["data"]["chunk"]))

                #Utils.log_info(f"Received chunk for file {message['data']['file_id']} with size {len(chunks_per_file[message['data']['file_id']])}.")

            elif message["status"] == WebsocketMessageStatus.FINAL_CHUNK:
                if message["data"]["file_id"] not in chunks_per_file:
                    chunks_per_file[message["data"]["file_id"]] = bytearray()
                chunks_per_file[message["data"]["file_id"]] += bytearray(b64decode(message["data"]["chunk"]))

                files_received[message["data"]["file_id"]] = b64encode(chunks_per_file[message["data"]["file_id"]]).decode('utf-8')
                
                del chunks_per_file[message["data"]["file_id"]]
    except Exception as e:
        internal_client.jobs -= 1
        del internal_client.on_progress_per_task[job_data["task_id"]]
        Utils.log_error(f"An error occurred: {e}")
        return JSONResponse(content={"status": WebsocketMessageStatus.ERROR, "error": str(e)})
    finally:
        internal_client.jobs -= 1
        internal_client.on_progress_per_task.pop(job_data["task_id"], None)
        chunks_per_file.clear()



@app.websocket('/')
async def handle_websocket(websocket: WebSocket):
    await websocket.accept()
    client_id = None
    id = None
    try:
        if "sec-websocket-protocol" in websocket.headers and  websocket.headers["sec-websocket-protocol"].startswith("processing-computer-internal"):
            id = websocket.headers["sec-websocket-protocol"].replace("processing-computer-internal-", "")
            Utils.log_info(f"Internal client connected: {id}")
            internal_clients[id] = WebsocketInternalClient(websocket, id)
            for client in clients.values():
                await client.send_text(json.dumps({"status": WebsocketMessageStatus.INTERNAL_CLIENT_REPORT, 'data': {"num_clients": len(internal_clients)}}))
            
            while True:
                message = await websocket.receive_text()
                message = json.loads(message)

                if message["status"] == WebsocketMessageStatus.PONG:
                    internal_clients[id].received_pong()
                    continue
                if message["status"] == WebsocketMessageStatus.PROGRESS:
                    if message["data"]["task_id"] in internal_clients[id].on_progress_per_task:
                        await internal_clients[id].on_progress_per_task[message["data"]["task_id"]](message["data"]["message"])
                else:
                    internal_clients[id].messages_per_task[message["data"]["task_id"]].put(message)
        else:
            await websocket.send_text(json.dumps({"status": WebsocketMessageStatus.INTERNAL_CLIENT_REPORT, 'data': {"num_clients": len(internal_clients)}}))
            client_id = None
            while True:
                message = await websocket.receive_json()
                Utils.log_info(f"message: {message}")
                if message["command"] == "send_id":
                    client_id = message["data"]
                    clients[client_id] = websocket
                    Utils.log_info(f"Client {client_id} connected.")
    except WebSocketDisconnect:
        if client_id:
            Utils.log_info(f"Connection with client {client_id} closed.")
            clients.pop(client_id, None)
        if id:
            await handle_internal_client_disconnect(id)
    except Exception as e:
        Utils.log_error(f"An error occurred: {e}")
    finally:

        if client_id and  client_id in clients:
            del clients[client_id]
        if id in internal_clients:
            handle_internal_client_disconnect(id)

async def handle_internal_client_disconnect(id):
    if internal_clients[id].jobs == 0:
        Utils.log_info(f"Removing internal client {id}.")
        del internal_clients[id]
    else:
        for task in internal_clients[id].messages_per_task:
            internal_clients[id].messages_per_task[task].put({"status": WebsocketMessageStatus.ERROR, "data": "Internal client disconnected."})
        del internal_clients[id]
    for client in clients.values():
        await client.send_text(json.dumps({"status": WebsocketMessageStatus.INTERNAL_CLIENT_REPORT, 'data': {"num_clients": len(internal_clients)}}))



@app.route("/")
async def root():
    return "Hello, World!"

if __name__ == "__main__":
    config = Config()
    config.bind = ["0.0.0.0:8080"]  # bind to localhost on port 8080
    asyncio.run(serve(app, config))
    #socketio.run(app,host='0.0.0.0',port=8000,log_output=True)