import asyncio
from base64 import b64decode, b64encode
from io import BytesIO
from typing import Dict
from fastapi import UploadFile
import websockets.client as websockets
import random
import json
from queue import SimpleQueue
from read_to_images import read_to_images
from websocket_types import WebsocketMessageCommand, WebsocketMessageStatus
from copy import deepcopy

CHUNK_SIZE = 1024   # 1Mb

class InternalClientMessageType:
    FILE_RECEIVED = "fileReceived"

class Environment:
    PROD = "PROD"
    DEV = "DEV"

    def get_environment():
        return Environment.DEV
    
def image_as_encoded(image):
    byte_arr = BytesIO()
    image.save(byte_arr, format='PNG') # convert the PIL image to byte array
    encoded_img = b64encode(byte_arr.getvalue()).decode('utf-8') # encode as base64
    return encoded_img

async def send_bytes_in_chunks(websocket: websockets.WebSocketClientProtocol,task_id: str, file_data: bytes,file_id: str):
    print(f"Sending file in chunks: {file_id}, size: {len(file_data)}")
    for i in range(0, len(file_data), CHUNK_SIZE):
        chunk = file_data[i:i+CHUNK_SIZE]
        status = WebsocketMessageStatus.SENDING_CHUNK
        if  i + CHUNK_SIZE >= len(file_data):
            status = WebsocketMessageStatus.FINAL_CHUNK
        await websocket.send(json.dumps({"status": status,'data': {
            'task_id': task_id,
            'chunk': b64encode(chunk).decode('utf-8'),
            "file_id": file_id
        }}))
    
chunks_per_file_id = {}
files_received: Dict[str,str] = {}
messages_per_task_id: Dict[str,SimpleQueue] = {}
    

async def handle_job_received(job,websocket: websockets.WebSocketClientProtocol):
    
    files_to_wait_for: list = deepcopy(job["file_ids"])

    while True:
        if  messages_per_task_id[job["task_id"]].empty():
            await asyncio.sleep(0.1)
            continue
        message = messages_per_task_id[job["task_id"]].get()
        
        if message["status"] == InternalClientMessageType.FILE_RECEIVED:
            files_to_wait_for.remove(message["data"]["file_id"])     

        if len(files_to_wait_for) > 0:        
            continue
    
        await send_progress(websocket, "All files received on internal client, starting job", job["task_id"])

        if job["command"] == WebsocketMessageCommand.READ_TO_IMAGES:
            await send_progress(websocket, "Starting to read PDF to images.", job["task_id"])


            images = {}
            for file_id in job["file_ids"]:

                print(f"Received file: {file_id} with size: {len(files_received[file_id])}")
                file = files_received[file_id]

                print(f"Decoded file: {len(file)}")


                uploadFile = UploadFile(
                    file=BytesIO(file),
                    filename=job["filename"]
                )

                images_inner = await read_to_images(uploadFile, on_progress=lambda x: send_progress(websocket, x, job["task_id"])) 
                await send_progress(websocket, "Completed reading PDF to images.", job["task_id"])
                
                for image in images_inner["images"]:
                    images_inner["images"][image] = image_as_encoded(images_inner["images"][image])

                for key in images_inner:
                    if key not in images:
                        images[key] = images_inner[key]
                    else:
                        images[key].append(images_inner[key])

        # send images back

        images_ids = []

        for image in images["images"]:

            images_ids.append(image)

            await send_bytes_in_chunks(websocket,job["task_id"], b64decode(images["images"][image]), image)
        
        del images["images"]
        
        await websocket.send(json.dumps({"status": WebsocketMessageStatus.COMPLETED_TASK, "data": {
            "task_id": job["task_id"],
            "images_ids": images_ids,
            **images
        }}))


async def send_progress(websocket: websockets.WebSocketClientProtocol, message, task_id):
    print(f"Sending progress: {message}")
    await websocket.send(json.dumps({"status": WebsocketMessageStatus.PROGRESS,'data': {
        'task_id': task_id,
        'message': message
    }}))

async def connect_to_websocket():
    uri = "wss://echo.websocket.org"

    if Environment.get_environment() == Environment.DEV:
        uri = "ws://localhost:8000"

    id = random.randbytes(16).hex()
    
    async with websockets.connect(uri,subprotocols=[f"processing-computer-internal-{id}"]) as websocket:
        print(f"Connected to websocket: {uri}")
        while True:
            try:
                response = await websocket.recv()
                #print(f"Received: {response}")
                response = json.loads(response)

                if response["data"]["task_id"] not in messages_per_task_id:
                    messages_per_task_id[response["data"]["task_id"]] = SimpleQueue()

                if "command" in response:
                    if response["command"] == WebsocketMessageCommand.READ_TO_IMAGES:
                        asyncio.create_task(handle_job_received({
                            "command": response["command"],
                            **response["data"]
                        },websocket))
                else:
                    if response["status"] == WebsocketMessageStatus.SENDING_CHUNK:
                        if response["data"]["file_id"] not in chunks_per_file_id:
                            chunks_per_file_id[response["data"]["file_id"]] = bytearray()
                        chunks_per_file_id[response["data"]["file_id"]] += bytearray(b64decode(response["data"]["chunk"]))
                        await send_progress(websocket, f'Received chunk on Internal Client, current size: {len(chunks_per_file_id[response["data"]["file_id"]])}', response["data"]["task_id"])

                    if response["status"] == WebsocketMessageStatus.FINAL_CHUNK:
                        print(f"Received final chunk for file: {response['data']['file_id']}")
                        chunks_per_file_id[response["data"]["file_id"]] += bytearray(b64decode(response["data"]["chunk"]))
                        files_received[response["data"]["file_id"]] = chunks_per_file_id[response["data"]["file_id"]]
                        del chunks_per_file_id[response["data"]["file_id"]]

                        await send_progress(websocket, f'Received final chunk on Internal Client, total size: {len(files_received[response["data"]["file_id"]])}', response["data"]["task_id"])

                        messages_per_task_id[response["data"]["task_id"]].put({"status": InternalClientMessageType.FILE_RECEIVED, "data": {
                            "file_id": response["data"]["file_id"]
                        }}) 

            except Exception as e:
                print(f"An error occurred: {e}")





if __name__ == "__main__":



    asyncio.run(connect_to_websocket())