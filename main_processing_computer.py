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
from find_circles import find_circles_cv2, find_circles_fallback
from read_to_images import read_to_images
from websocket_types import BoxRectangleType, WebsocketMessageCommand, WebsocketMessageStatus
from copy import deepcopy
from utils import Utils

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

async def send_bytes_in_chunks(websocket: websockets.WebSocketClientProtocol,task_id: str, file_data: bytes,file_id: str):
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
    

async def handle_job_received(job,websocket: websockets.WebSocketClientProtocol):
    

    #Utils.log_info(f"Received job: {job}")

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

                Utils.log_info(f"Received file: {file_id} with size: {len(files_received[file_id])}")
                file = files_received[file_id]

                Utils.log_info(f"Decoded file: {len(file)}")


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

            await send_progress(websocket, "Sending images back to server...", job["task_id"])
            
            images_ids = []
            index = 0
            for image in images["images"]:

                images_ids.append(image)

                await send_progress(websocket, f"Sending images back to server {index}/{len(images['images'])}...", job["task_id"])

                await send_bytes_in_chunks(websocket,job["task_id"], b64decode(images["images"][image]), image)

                index += 1
            del images["images"]

            for file_id in job["file_ids"]:
                del files_received[file_id]
            
            
            
            await websocket.send(json.dumps({"status": WebsocketMessageStatus.COMPLETED_TASK, "data": {
                "task_id": job["task_id"],
                "images_ids": images_ids,
                **images
            }}))

            del messages_per_task_id[job["task_id"]]

            return
        elif job["command"] == WebsocketMessageCommand.FIND_CIRCLES:

            await send_progress(websocket, "Starting to finding circles in images.", job["task_id"])
            
            data = job
            circles_final = {}
            
            for file_id in job["file_ids"]:

                file = files_received[file_id]

                image = Image.open(BytesIO(file))

                await send_progress(websocket, f"Processing image: {file_id}", job["task_id"])

                image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

                if "image_offset" in data and data["image_offset"] != None:
                    M = np.float32([[1, 0, data["image_offset"]["x"]], [0, 1, data["image_offset"]["y"]]])
                    image = cv2.warpAffine(image, M, image.shape[1::-1], flags=cv2.INTER_LINEAR)
                    Utils.log_info(f'Transformed image with offset: {data["image_offset"]}')

                if "image_angle" in data and data["image_angle"] != None:
                    center = (image.shape[1] // 2, image.shape[0] // 2)
                    M = cv2.getRotationMatrix2D(center, -data["image_angle"], 1)
                    image = cv2.warpAffine(image, M, image.shape[1::-1])
                    Utils.log_info(f'Rotated image with angle: {data["image_angle"]}')

                Utils.log_info(f'Circle precision percentage: {data["circle_precision_percentage"]}')

                Utils.log_info(f"Data in request = {data}")


                if "circle_precision_percentage" not in data:
                    data["circle_precision_percentage"] = 1


                circles_per_box = {}

                has_template_circles = "template_circles" in data["boxes"][0] and  data["boxes"][0]["template_circles"] != None

                #Utils.log_info(f"Has template circles: {has_template_circles} | {data['boxes'][0]}")

                if has_template_circles and not data["use_fallback_method"]:
                    training_data = Utils.load_training_data_for_circles_optimization()
                    if f'{data["filename"]}_{data["socket_id"]}' not in training_data:
                        training_data[f'{data["filename"]}_{data["socket_id"]}'] = {}

                    circles_data_for_training = []



                # sort boxes with exemplo circles first

                data["boxes"] = sorted(data["boxes"], key=lambda x: 0 if x["rect_type"] == BoxRectangleType.EXEMPLO_CIRCULO else 1)


                for box in data["boxes"]:

                    rect = box["rect"]
                    rect_type = box["rect_type"]
                    box_name = box["name"]
                    circle_size = data["circle_size"] if "circle_size" in data else None
                    if rect_type == BoxRectangleType.EXEMPLO_CIRCULO:
                        circle_size = None

                    if has_template_circles and data["use_fallback_method"]:
                        Utils.log_info(f"Finding circles for box: {box_name} using template circles method. (fallback)")

                        circles = await find_circles_fallback("",
                            rect,
                            rectangle_type=rect_type,
                            template_circles=box["template_circles"],
                            darkness_threshold=data["darkness_threshold"],
                            img=image,
                            on_progress= lambda x: send_progress(websocket, x, job["task_id"])
                                                              )
                        
                    else:

                        Utils.log_info(f"Finding circles for box: {box_name} using VC method. (computer vision)")




                        circles = await find_circles_cv2("", rect, rect_type, 
                                                        img=image,
                                                        circle_size=circle_size,
                                                        dp=data["inverse_ratio_accumulator_resolution"],
                                                        darkness_threshold=data["darkness_threshold"],
                                                        circle_precision_percentage=data["circle_precision_percentage"],
                                                        param2=data["param2"],
                                                        on_progress= lambda x: send_progress(websocket, x, job["task_id"]))

                    if rect_type == BoxRectangleType.EXEMPLO_CIRCULO and len(circles) > 0:
                        data["circle_size"] = circles[0]["radius"] / image.shape[1]

                    if has_template_circles and not data["use_fallback_method"]: 

                        circles_data_for_training.append({
                            "circles": list(map(lambda x: {
                                "center_x": x["center_x"],
                                "center_y": x["center_y"],
                                "radius": x["radius"],
                            },circles)),
                            "template_circles": list(map(lambda x: {
                                "center_x": x["center_x"],
                                "center_y": x["center_y"],
                                "radius": x["radius"],
                            },box["template_circles"])),
                        })



                    await send_progress(websocket, "Completed processing image.", job["task_id"])

                    if "image_offset" in data and data["image_offset"] != None:
                        for circle in circles:
                            circle["center_x"] = circle["center_x"] - data["image_offset"]["x"]
                            circle["center_y"] = circle["center_y"] - data["image_offset"]["y"]

                    if "image_angle" in data and data["image_angle"] != None:
                        center = (image.shape[1] // 2, image.shape[0] // 2)
                        M = cv2.getRotationMatrix2D(center, data["image_angle"], 1)
                        for circle in circles:
                            circle["center_x"],circle["center_y"] = cv2.transform(np.array([[circle["center_x"],circle["center_y"]]]).reshape(-1,1,2), M).reshape(2)

                    #if rect_type == BoxRectangleType.EXEMPLO_CIRCULO:

                    for circle in circles:
                        circle["center_x"] = circle["center_x"] / image.shape[1]
                        circle["center_y"] = circle["center_y"] / image.shape[0]
                        circle["radius"] = circle["radius"] / image.shape[1]

                    circles_per_box[box_name] = circles

                

                circles_final[file_id] = circles_per_box
            
                del files_received[file_id]


                if has_template_circles and not data["use_fallback_method"]:

                    with open("training_images/" + f'{data["filename"]}_{data["socket_id"]}.png', "wb") as f:
                        f.write(file)

                    training_data[f'{data["filename"]}_{data["socket_id"]}'][Utils.random_hex(20)] = {
                        "data": {
                                    "dp": data["inverse_ratio_accumulator_resolution"],
                                    "circle_precision_percentage": data["circle_precision_percentage"],
                                    "param2": data["param2"]
                                },
                        "circles_data": circles_data_for_training,
                        "image": f'{data["filename"]}_{data["socket_id"]}.png'
                    }

                    Utils.save_training_data_for_circles_optimization(training_data)


            await websocket.send(json.dumps({"status": WebsocketMessageStatus.COMPLETED_TASK, "data": {
                "task_id": job["task_id"],
                "circles": circles_final
            }}))

            del messages_per_task_id[job["task_id"]]

            return


async def send_progress(websocket: websockets.WebSocketClientProtocol, message, task_id):
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
            async with websockets.connect(uri,subprotocols=[f"processing-computer-internal-{Utils.get_version()}-{id}"]) as websocket:
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
                                Utils.log_info(f"Received final chunk for file: {response['data']['file_id']}")
                                chunks_per_file_id[response["data"]["file_id"]] += bytearray(b64decode(response["data"]["chunk"]))
                                files_received[response["data"]["file_id"]] = chunks_per_file_id[response["data"]["file_id"]]
                                del chunks_per_file_id[response["data"]["file_id"]]

                                await send_progress(websocket, f'Received final chunk on Internal Client, total size: {len(files_received[response["data"]["file_id"]])}', response["data"]["task_id"])

                                messages_per_task_id[response["data"]["task_id"]].put({"status": InternalClientMessageType.FILE_RECEIVED, "data": {
                                    "file_id": response["data"]["file_id"]
                                }}) 

                            if response["status"] == WebsocketMessageStatus.ERROR:
                                Utils.log_error(f"Received error: {response['data']['message']}")
                                break
                    except ConnectionClosedError as e:
                        Utils.log_error(f"Connection closed: {e}")
                        break
                    except Exception as e:
                        Utils.log_error(f"An error occurred: {e}")
        except (ConnectionClosedError, OSError):
                Utils.log_error("Connection lost... retrying in 5 seconds")
                await asyncio.sleep(5)  # Wait for 5 seconds before retrying




if __name__ == "__main__":

    #Utils.set_debug(True)

    asyncio.run(connect_to_websocket())