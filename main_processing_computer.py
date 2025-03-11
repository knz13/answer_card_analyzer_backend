import asyncio
from base64 import b64decode, b64encode
from io import BytesIO
from typing import Dict
from PIL import Image
import cv2
from fastapi import UploadFile
import numpy as np
import websockets.client as websockets
from websockets.exceptions import ConnectionClosedError
import random
import json
from queue import SimpleQueue

from websockets.uri import WebSocketURI
from find_circles import find_circles_cv2, find_circles_fallback
from read_to_images import read_to_images
from websocket_types import BoxRectangleType, WebsocketMessageCommand, WebsocketMessageStatus
from copy import deepcopy
from utils import Utils
from websockets.asyncio.client import connect
import psutil
import os
import sys

MEMORY_THRESHOLD_PERCENT = 90  # Set threshold for max memory usage
CHUNK_SIZE = 1024 * 200  # 200kb

class InternalClientMessageType:
    FILE_RECEIVED = "fileReceived"

class Environment:
    PROD = "PROD"
    DEV = "DEV"

    def get_environment():
        return Environment.PROD
    
def image_as_encoded(image):
    byte_arr = BytesIO()
    image.save(byte_arr, format='PNG') # convert the PIL image to byte array
    encoded_img = b64encode(byte_arr.getvalue()).decode('utf-8') # encode as base64
    return encoded_img

async def send_bytes_in_chunks(websocket: websockets.ClientProtocol,task_id: str, file_data: bytes,file_id: str):
    Utils.log_info(f"Sending file in chunks: {file_id}, size: {len(file_data)}")
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
files_received: Dict[str,bytearray] = {}
messages_per_task_id: Dict[str,SimpleQueue] = {}
    

async def handle_job_received(job,websocket: websockets.ClientProtocol):
    try:
        files_to_wait_for: list = deepcopy(job["file_ids"])

        # Create task queue if it doesn't exist
        if job["task_id"] not in messages_per_task_id:
            messages_per_task_id[job["task_id"]] = SimpleQueue()

        while True:
            if messages_per_task_id[job["task_id"]].empty():
                await asyncio.sleep(0.1)
                continue
            message = messages_per_task_id[job["task_id"]].get()
            
            if message["status"] == InternalClientMessageType.FILE_RECEIVED:
                files_to_wait_for.remove(message["data"]["file_id"])     

            if len(files_to_wait_for) > 0:     
                continue

            await send_progress(websocket, "All files received on internal client, starting job", job["task_id"])
            
            try:
                if job["command"] == WebsocketMessageCommand.READ_TO_IMAGES:
                    await handle_read_to_images(job, websocket)
                elif job["command"] == WebsocketMessageCommand.FIND_CIRCLES:
                    await handle_find_circles(job, websocket)
            finally:
                # Clean up resources
                for file_id in job["file_ids"]:
                    if file_id in files_received:
                        del files_received[file_id]
                    if file_id in chunks_per_file_id:
                        del chunks_per_file_id[file_id]
                if job["task_id"] in messages_per_task_id:
                    del messages_per_task_id[job["task_id"]]
            return
    except Exception as e:
        Utils.log_error(f"Error in handle_job_received: {str(e)}")
        try:
            await websocket.send(json.dumps({
                "status": WebsocketMessageStatus.ERROR,
                "data": {
                    "task_id": job["task_id"],
                    "error": str(e)
                }
            }))
        except:
            pass
        # Clean up on error
        for file_id in job.get("file_ids", []):
            if file_id in files_received:
                del files_received[file_id]
            if file_id in chunks_per_file_id:
                del chunks_per_file_id[file_id]
        if job.get("task_id") in messages_per_task_id:
            del messages_per_task_id[job["task_id"]]

async def handle_read_to_images(job, websocket):
    await send_progress(websocket, "Starting to read PDF to images.", job["task_id"])
    images = {}
    
    for file_id in job["file_ids"]:
        try:
            if file_id not in files_received:
                raise Exception(f"File {file_id} not found")

            Utils.log_info(f"Processing file: {file_id} with size: {len(files_received[file_id])}")
            file = files_received[file_id]

            uploadFile = UploadFile(
                file=BytesIO(file),
                filename=job["filename"]
            )

            images_inner = await read_to_images(uploadFile, on_progress=lambda x: send_progress(websocket, x, job["task_id"]))
            await send_progress(websocket, "Completed reading PDF to images.", job["task_id"])
            
            for image in images_inner["images"]:
                try:
                    images_inner["images"][image] = image_as_encoded(images_inner["images"][image])
                except Exception as e:
                    Utils.log_error(f"Error encoding image {image}: {str(e)}")
                    continue

            for key in images_inner:
                if key not in images:
                    images[key] = images_inner[key]
                else:
                    images[key].extend(images_inner[key])

        except Exception as e:
            Utils.log_error(f"Error processing file {file_id}: {str(e)}")
            raise

    await send_progress(websocket, "Sending images back to server...", job["task_id"])
    
    images_ids = []
    for index, image in enumerate(images.get("images", {})):
        images_ids.append(image)
        await send_progress(websocket, f"Sending images back to server {index}/{len(images['images'])}...", job["task_id"])
        await send_bytes_in_chunks(websocket, job["task_id"], b64decode(images["images"][image]), image)

    if "images" in images:
        del images["images"]
    
    await websocket.send(json.dumps({
        "status": WebsocketMessageStatus.COMPLETED_TASK,
        "data": {
            "task_id": job["task_id"],
            "images_ids": images_ids,
            **images
        }
    }))

async def handle_find_circles(job, websocket):
    await send_progress(websocket, "Starting to finding circles in images.", job["task_id"])
    circles_final = {}
    
    for file_id in job["file_ids"]:
        try:
            if file_id not in files_received:
                raise Exception(f"File {file_id} not found")

            file = files_received[file_id]
            
            try:
                image = Image.open(BytesIO(file))
                cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                image.close()  # Explicitly close PIL Image
            except Exception as e:
                Utils.log_error(f"Error loading image {file_id}: {str(e)}")
                continue

            await send_progress(websocket, f"Processing image: {file_id}", job["task_id"])

            # Apply image transformations
            if job.get("image_offset"):
                M = np.float32([[1, 0, job["image_offset"]["x"]], [0, 1, job["image_offset"]["y"]]])
                cv_image = cv2.warpAffine(cv_image, M, cv_image.shape[1::-1], flags=cv2.INTER_LINEAR)

            if job.get("image_angle") is not None:
                center = (cv_image.shape[1] // 2, cv_image.shape[0] // 2)
                M = cv2.getRotationMatrix2D(center, -job["image_angle"], 1)
                cv_image = cv2.warpAffine(cv_image, M, cv_image.shape[1::-1])

            circles_per_box = {}
            
            # Sort boxes with exemplo circles first
            boxes = sorted(job.get("boxes", []), key=lambda x: 0 if x.get("rect_type") == BoxRectangleType.EXEMPLO_CIRCULO else 1)

            for box in boxes:
                try:
                    rect = box.get("rect")
                    rect_type = box.get("rect_type")
                    box_name = box.get("name")
                    
                    if not all([rect, rect_type, box_name]):
                        continue

                    circle_size = job.get("circle_size")
                    if rect_type == BoxRectangleType.EXEMPLO_CIRCULO:
                        circle_size = None

                    if job.get("use_fallback_method") and box.get("template_circles"):
                        circles = await find_circles_fallback("",
                            rect,
                            rectangle_type=rect_type,
                            template_circles=box["template_circles"],
                            darkness_threshold=job.get("darkness_threshold", 0),
                            img=cv_image,
                            on_progress=lambda x: send_progress(websocket, x, job["task_id"])
                        )
                    else:
                        circles = await find_circles_cv2("", rect, rect_type, 
                            img=cv_image,
                            circle_size=circle_size,
                            dp=job.get("inverse_ratio_accumulator_resolution", 1),
                            darkness_threshold=job.get("darkness_threshold", 0),
                            circle_precision_percentage=job.get("circle_precision_percentage", 1),
                            param2=job.get("param2", 30),
                            on_progress=lambda x: send_progress(websocket, x, job["task_id"])
                        )

                    # Process circles
                    if rect_type == BoxRectangleType.EXEMPLO_CIRCULO and circles:
                        job["circle_size"] = circles[0]["radius"] / cv_image.shape[1]

                    for circle in circles:
                        # Normalize coordinates
                        if job.get("image_offset"):
                            circle["center_x"] -= job["image_offset"]["x"]
                            circle["center_y"] -= job["image_offset"]["y"]

                        if job.get("image_angle") is not None:
                            center = (cv_image.shape[1] // 2, cv_image.shape[0] // 2)
                            M = cv2.getRotationMatrix2D(center, job["image_angle"], 1)
                            circle["center_x"], circle["center_y"] = cv2.transform(
                                np.array([[circle["center_x"],circle["center_y"]]]).reshape(-1,1,2),
                                M
                            ).reshape(2)

                        # Normalize to image dimensions
                        circle["center_x"] /= cv_image.shape[1]
                        circle["center_y"] /= cv_image.shape[0]
                        circle["radius"] /= cv_image.shape[1]

                    circles_per_box[box_name] = circles

                except Exception as e:
                    Utils.log_error(f"Error processing box {box_name}: {str(e)}")
                    circles_per_box[box_name] = []

            circles_final[file_id] = circles_per_box

        except Exception as e:
            Utils.log_error(f"Error processing file {file_id}: {str(e)}")
            circles_final[file_id] = {}

    await websocket.send(json.dumps({
        "status": WebsocketMessageStatus.COMPLETED_TASK,
        "data": {
            "task_id": job["task_id"],
            "circles": circles_final
        }
    }))

async def send_progress(websocket: websockets.ClientProtocol, message, task_id):
    Utils.log_info(f"Sending progress: {message}")
    await websocket.send(json.dumps({"status": WebsocketMessageStatus.PROGRESS,'data': {
        'task_id': task_id,
        'message': message
    }}))

async def connect_to_websocket():
    uri = "wss://orca-app-h5tlv.ondigitalocean.app"

    if Environment.get_environment() == Environment.DEV:
        uri = "ws://localhost:8080"

    id = random.randbytes(32).hex()
    while True:
        try: 
            async with connect(uri,subprotocols=[f"processing-computer-internal-{Utils.get_version()}-{id}"]) as websocket:
                Utils.log_info(f"Connected to websocket: {uri}")
                while True:
                    try:
                        response = await websocket.recv()
                        #Utils.log_info(f"Received: {response}")
                        response = json.loads(response)
                        


                        

                        if type(response["data"]) == dict and response["data"]["task_id"] not in messages_per_task_id:
                            messages_per_task_id[response["data"]["task_id"]] = SimpleQueue()


                        
                        if "command" in response:
                            if response["command"] == WebsocketMessageCommand.READ_TO_IMAGES or response["command"] == WebsocketMessageCommand.FIND_CIRCLES:
                                Utils.log_info(f"len of files: {len(files_received)}, len of chunks: {len(chunks_per_file_id)}, len of messages: {len(messages_per_task_id)}")
                                asyncio.create_task(handle_job_received({
                                    "command": response["command"],
                                    **response["data"]
                                },websocket))
                            if response["command"] == WebsocketMessageCommand.PING:
                                await websocket.send(json.dumps({"status": WebsocketMessageStatus.PONG}))
                        else:
                            

                            if response["status"] == WebsocketMessageStatus.SENDING_CHUNK:
                                if response["data"]["file_id"] not in chunks_per_file_id:
                                    chunks_per_file_id[response["data"]["file_id"]] = bytearray()
                                chunks_per_file_id[response["data"]["file_id"]] += bytearray(b64decode(response["data"]["chunk"]))
                                #await send_progress(websocket, f'Received chunk on Internal Client, current size: {len(chunks_per_file_id[response["data"]["file_id"]])}', response["data"]["task_id"])
                            
                            if response["status"] == WebsocketMessageStatus.FINAL_CHUNK:

                                if response["data"]["file_id"] not in chunks_per_file_id:
                                    chunks_per_file_id[response["data"]["file_id"]] = bytearray()

                                Utils.log_info(f"Received final chunk for file: {response['data']['file_id']}")
                                chunks_per_file_id[response["data"]["file_id"]] += bytearray(b64decode(response["data"]["chunk"]))
                                files_received[response["data"]["file_id"]] = chunks_per_file_id[response["data"]["file_id"]]
                                del chunks_per_file_id[response["data"]["file_id"]]

                                await send_progress(websocket, f'Received final chunk on Internal Client, total size: {len(files_received[response["data"]["file_id"]])}', response["data"]["task_id"])

                                messages_per_task_id[response["data"]["task_id"]].put({"status": InternalClientMessageType.FILE_RECEIVED, "data": {
                                    "file_id": response["data"]["file_id"]
                                }}) 

                            if response["status"] == WebsocketMessageStatus.ERROR:
                                Utils.log_error(f"Received error: {response['error']}")
                                break
                    except ConnectionClosedError as e:
                        Utils.log_error(f"Connection closed: {e}")
                        break
                    except Exception as e:
                        Utils.log_error(f"An error occurred: {e}")
        
        except Exception as e:
                Utils.log_error(f"An error occurred while connecting to websocket: {e}")

        finally:
            Utils.log_info("Connection closed... retrying in 5 seconds")
            await asyncio.sleep(5)


async def monitor_memory():
    """
    Monitors the memory usage and restarts the script if memory exceeds a threshold.
    Prints memory usage stats every 5 minutes.
    """
    process = psutil.Process(os.getpid())  # Get current process info
    print_counter = 0  # Counter for printing memory stats
    
    while True:
        mem_info = process.memory_info()
        system_memory = psutil.virtual_memory()
        used_memory_percent = system_memory.percent
        
        # Print memory stats every 5 minutes (60 iterations with 5-second sleep)
        if print_counter >= 60:
            print("\nMemory Usage Stats:")
            print(f"Process RSS (Physical RAM Used): {mem_info.rss / 1024 / 1024:.2f} MB")
            print(f"Process VMS (Total Virtual Memory): {mem_info.vms / 1024 / 1024:.2f} MB")
            print(f"System Memory Used: {used_memory_percent:.1f}%")
            print(f"System Memory Available: {system_memory.available / 1024 / 1024:.2f} MB")
            print(f"System Memory Total: {system_memory.total / 1024 / 1024:.2f} MB")
            print("-" * 60)
        
        if used_memory_percent > MEMORY_THRESHOLD_PERCENT:
            print(f"Memory usage is too high ({used_memory_percent}%). Restarting the script.")
            await reset_script()

        await asyncio.sleep(2)  # Check every 5 seconds
        print_counter += 1

async def reset_script():
    """
    Resets the script by terminating the current process and restarting it.
    """
    print("Resetting the script...")

    # check if python or python3 is available

    if sys.executable:
        os.execv(sys.executable, [sys.executable] + sys.argv)

async def main():
    # Start memory monitoring task
    asyncio.create_task(monitor_memory())
    
    # Your existing asyncio tasks...
    await connect_to_websocket()  # Example of existing main function

if __name__ == "__main__":
    Utils.set_debug(False)
    asyncio.run(main())