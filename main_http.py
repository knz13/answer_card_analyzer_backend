import asyncio
from typing import Dict, List
import cv2
import numpy as np
from PIL import Image
import os
from base64 import b64decode, b64encode
from find_circles import find_circles, find_circles_cv2, show_image
from read_to_images import read_to_images
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


class WebsocketInternalClient:
    def __init__(self,websocket: WebSocket, id: str):
        self.websocket = websocket
        self.id = id
        self.jobs = 0
        self.messages_per_task: Dict[str,SimpleQueue] = {}
        self.on_progress_per_task = {}
    
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

app = FastAPI()


clients = {}  # Dictionary to track WebSocket sessions by ID
internal_clients: Dict[str,WebsocketInternalClient] = {}  # Dictionary to track WebSocket sessions by ID

async def send_progress(websocket: WebSocket, message, task_id):
    await websocket.send_text(json.dumps({"status": WebsocketMessageStatus.PROGRESS,'data': {
        'task_id': task_id,
        'message': message
    }}))

CHUNK_SIZE = 1024  # 1Mb

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
    print(f"Sending job to internal client {client_id}")

    

    socket = internal_clients[client_id]

    
    socket.messages_per_task[job.data["task_id"]] = SimpleQueue()

    internal_clients[client_id].jobs += 1

    await socket.websocket.send_text(json.dumps({
        "command": job.command,
        "data": job.data
    }))

    await socket.websocket.send_text(json.dumps({
        "command": job.command,
        "data": job.data
    }))
    
    for file_id in job.files:
        await send_bytes_in_chunks(socket.websocket,job.data["task_id"],job.files[file_id],file_id)
    
    

@app.post("/read_to_images")
async def read_to_images_route(file: UploadFile = File(...), task_id: str = Form(...), socket_id: str = Form(...)):
    print("Received request to read PDF to images.")
    print(f"Received file: {file.filename}")

    print(f"Socket ID: {socket_id}, websocket: {clients[socket_id]}")

    if len(internal_clients) == 0:
        raise HTTPException(status_code=404, detail="No internal clients connected.")
    
    chosen_internal_client = random.choice(list(internal_clients.keys()))
    
    file_id = random.randbytes(16).hex()

    job = WebsocketInternalClientJob(WebsocketMessageCommand.READ_TO_IMAGES, {
        "task_id": task_id,
        "filename": file.filename,
    }, {file_id: await file.read()})
    
    response = await handle_internal_client_task(internal_clients[chosen_internal_client], job,on_progress=lambda x: send_progress(clients[socket_id], x, task_id) if socket_id in clients else None)

    if type(response) == JSONResponse:
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
    print("Received request to find circles.")
    print(f"Received file: {file.filename}")
    
    if len(internal_clients) == 0:
        raise HTTPException(status_code=404, detail="No internal clients connected.")

    try:
        data = json.loads(data)
        #print(f"Received data: {data}")

        if socket_id in clients:
            await send_progress(clients[socket_id], "Starting to process image for circles.", task_id)

        file_data = await file.read()

        image = Image.open(io.BytesIO(file_data))

        image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        if "image_offset" in data and data["image_offset"] != None:
            M = np.float32([[1, 0, data["image_offset"]["x"]], [0, 1, data["image_offset"]["y"]]])
            image = cv2.warpAffine(image, M, image.shape[1::-1], flags=cv2.INTER_LINEAR)
            print(f'Transformed image with offset: {data["image_offset"]}')

        if "image_angle" in data and data["image_angle"] != None:
            center = (image.shape[1] // 2, image.shape[0] // 2)
            M = cv2.getRotationMatrix2D(center, -data["image_angle"], 1)
            image = cv2.warpAffine(image, M, image.shape[1::-1])
            print(f'Rotated image with angle: {data["image_angle"]}')

        print(f'Circle precision percentage: {data["circle_precision_percentage"]}')

        if data["circle_precision_percentage"] == None:
            data["circle_precision_percentage"] = 1

        circles = await find_circles_cv2("", data["rect"], data["rect_type"], img=image, circle_precision_percentage=data["circle_precision_percentage"],
                                         on_progress= lambda x: send_progress(clients[socket_id], x, task_id) if socket_id in clients else None)

        if socket_id in clients:
            await send_progress(clients[socket_id], "Completed processing image.", task_id)

        if "image_offset" in data and data["image_offset"] != None:
            for circle in circles:
                circle["center_x"] = circle["center_x"] - data["image_offset"]["x"]
                circle["center_y"] = circle["center_y"] - data["image_offset"]["y"]

        if "image_angle" in data and data["image_angle"] != None:
            center = (image.shape[1] // 2, image.shape[0] // 2)
            M = cv2.getRotationMatrix2D(center, data["image_angle"], 1)
            for circle in circles:
                circle["center_x"],circle["center_y"] = cv2.transform(np.array([[circle["center_x"],circle["center_y"]]]).reshape(-1,1,2), M).reshape(2)

        if socket_id in clients:
            await send_progress(clients[socket_id], "Completed processing image.", task_id)
        return JSONResponse(content={"status": WebsocketMessageStatus.COMPLETED_TASK, "data": circles})
    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

async def handle_internal_client_task(internal_client: WebsocketInternalClient, job: WebsocketInternalClientJob,on_progress=None):

    job_data = {
        "file_ids": list(job.files.keys()),
        **job.data
    }

    if len(internal_clients) == 0:
        raise HTTPException(status_code=404, detail="No internal clients connected.")
    
    print(f"Received files: {len(job.files)}")
    print(f"Socket ID: {internal_client.id}, websocket: {internal_client.websocket}")
    if job.command == WebsocketMessageCommand.READ_TO_IMAGES:
        print("Received request to read PDF to images.")

    elif job.command == WebsocketMessageCommand.FIND_CIRCLES:
        print("Received request to find circles.")
        
    try:

        internal_client.on_progress_per_task[job_data["task_id"]] = on_progress
        
        # send job to internal client

        await send_job_to_internal_client(internal_client.id, WebsocketInternalClientJob(
            job.command,
            job_data,
            job.files
        ))

        print(f"Sent job to internal client {internal_client.id}.")

        chunks_per_file = {}
        files_received = {}

        while True:
            if internal_client.messages_per_task[job_data["task_id"]].empty():
                await asyncio.sleep(0.1)
                continue

            message = internal_client.messages_per_task[job_data["task_id"]].get()
            print(f'Internal message on task "{job.data["task_id"]}": {message["status"]}')

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

                #print(f"Received chunk for file {message['data']['file_id']} with size {len(chunks_per_file[message['data']['file_id']])}.")

            elif message["status"] == WebsocketMessageStatus.FINAL_CHUNK:
                if message["data"]["file_id"] not in chunks_per_file:
                    chunks_per_file[message["data"]["file_id"]] = bytearray()
                chunks_per_file[message["data"]["file_id"]] += bytearray(b64decode(message["data"]["chunk"]))

                files_received[message["data"]["file_id"]] = b64encode(chunks_per_file[message["data"]["file_id"]]).decode('utf-8')

                del chunks_per_file[message["data"]["file_id"]]

    except Exception as e:
        internal_client.jobs -= 1
        del internal_client.on_progress_per_task[job_data["task_id"]]
        print(f"An error occurred: {e}")
        return JSONResponse(content={"status": WebsocketMessageStatus.ERROR, "error": str(e)})
        
@app.websocket('/')
async def handle_websocket(websocket: WebSocket):
    await websocket.accept()
    if "sec-websocket-protocol" in websocket.headers and  websocket.headers["sec-websocket-protocol"].startswith("processing-computer-internal"):
        id = websocket.headers["sec-websocket-protocol"].replace("processing-computer-internal-","")

        print(f"Internal client connected: {id}")

        internal_clients[id] = WebsocketInternalClient(websocket,id)
        try:
            while True:
                message = await websocket.receive_text()
                #print(f"Internal message: {message}")
                message = json.loads(message)
                if message["status"] == WebsocketMessageStatus.PROGRESS:
                    if message["data"]["task_id"] in internal_clients[id].on_progress_per_task:
                        await internal_clients[id].on_progress_per_task[message["data"]["task_id"]](message["data"]["message"])
                else:  
                    internal_clients[id].messages_per_task[message["data"]["task_id"]].put(message)

        except WebSocketDisconnect:
            print(f"Internal connection with {id} closed normally.")
        except Exception as e:
                print(f"An error occurred: {e}")
        finally:

            if internal_clients[id].jobs == 0:
                print(f"Removing internal client {id}.")
                del internal_clients[id]
            else:
                print(f"Adding message to remove client {id}")
                for task in internal_clients[id].messages_per_task:
                    internal_clients[id].messages_per_task[task].put({"status": WebsocketMessageStatus.ERROR,"data": "Internal client disconnected."})
            
    else:
        try:
            while True:
                message = await websocket.receive_json()
                print(f"message: {message}")
                if message["command"] == "send_id":
                    client_id = message["data"]
                    clients[client_id] = websocket
                    print(f"Client {client_id} connected.")
        except WebSocketDisconnect:
            print(f"Connection with client {client_id} closed.")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            client_id = list(clients.keys())[list(clients.values()).index(websocket)]
            del clients[client_id]


if __name__ == "__main__":
    config = Config()
    config.bind = ["0.0.0.0:8000"]  # bind to localhost on port 8080
    asyncio.run(serve(app, config))
    #socketio.run(app,host='0.0.0.0',port=8000,log_output=True)