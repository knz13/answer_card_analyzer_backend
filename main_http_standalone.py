import asyncio
import cv2
import numpy as np
from PIL import Image
import os
from base64 import b64encode
from find_circles import find_circles, find_circles_cv2, show_image
from read_to_images import read_to_images
from websocket_types import WebsocketMessageCommand, WebsocketMessageStatus
import json
import io
from hypercorn.config import Config
from hypercorn.asyncio import serve
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket



def image_as_encoded(image):
    byte_arr = io.BytesIO()
    image.save(byte_arr, format='PNG') # convert the PIL image to byte array
    encoded_img = b64encode(byte_arr.getvalue()).decode('utf-8') # encode as base64
    return encoded_img

app = FastAPI()


clients = {}  # Dictionary to track WebSocket sessions by ID

async def send_progress(websocket: WebSocket, message, task_id):
    await websocket.send_text(json.dumps({"status": WebsocketMessageStatus.PROGRESS,'data': {
        'task_id': task_id,
        'message': message
    }}))


@app.post("/read_to_images")
async def read_to_images_route(file: UploadFile = File(...), task_id: str = Form(...), socket_id: str = Form(...)):
    print("Received request to read PDF to images.")
    print(f"Received file: {file.filename}")

    print(f"Socket ID: {socket_id}, websocket: {clients[socket_id]}")



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
        print(f"An error occurred: {e.__traceback__}")
        raise HTTPException(status_code=500, detail=str(e))

        
@app.websocket('/')
async def handle_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_json()
            print(f"message: {message}")
            if message["command"] == "send_id":
                client_id = message["data"]
                clients[client_id] = websocket
                print(f"Client {client_id} connected.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client_id = list(clients.keys())[list(clients.values()).index(websocket)]
        print(f"Connection with {client_id} closed.")
        del clients[client_id]


if __name__ == "__main__":
    config = Config()
    config.bind = ["0.0.0.0:8000"]  # bind to localhost on port 8080
    asyncio.run(serve(app, config))
    #socketio.run(app,host='0.0.0.0',port=8000,log_output=True)