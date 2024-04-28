import asyncio
import websockets
from quart import  Quart, Response, request, jsonify
import cv2
import numpy as np
from PIL import Image
import os
from base64 import b64encode
import tempfile
from find_circles import find_circles, find_circles_cv2, show_image
from read_to_images import read_to_images
from websocket_types import WebsocketMessageCommand, WebsocketMessageStatus
import json
import io
from quart.datastructures import FileStorage
from quart_cors import cors
from hypercorn.config import Config
from hypercorn.asyncio import serve


def image_as_encoded(image):
    byte_arr = io.BytesIO()
    image.save(byte_arr, format='PNG') # convert the PIL image to byte array
    encoded_img = b64encode(byte_arr.getvalue()).decode('utf-8') # encode as base64
    return encoded_img

app = Quart(__name__)
app = cors(app, allow_origin="*")

clients = {}  # Dictionary to track WebSocket sessions by ID

async def send_progress(websocket, message, task_id):
    await websocket.send(json.dumps({"status": WebsocketMessageStatus.PROGRESS,'data': {
        'task_id': task_id,
        'message': message
    }}))



@app.route("/read_to_images", methods=['POST'])
async def read_to_images_route():
    print("Received request to read PDF to images.")

    files = await request.files
    file: FileStorage = files['file']
    print(f"Received file: {file.filename}")
    form = await request.form

    additional_data = form.to_dict()

    task_id = additional_data.get('task_id')

    print(additional_data)
    client_id = additional_data.get('socket_id')

    

    try:
        if client_id in clients:
            await send_progress(clients[client_id], "Starting to read PDF to images.", task_id)
        images = await read_to_images(file, additional_data,on_progress=lambda x: send_progress(clients[client_id], x, task_id) if client_id in clients else None) 
        if client_id in clients:
            await send_progress(clients[client_id], "Completed reading PDF to images.", task_id)
        
        for image in images["images"]:
            images["images"][image] = image_as_encoded(images["images"][image])

        return jsonify({"status": WebsocketMessageStatus.COMPLETED_TASK, "data": images})
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"status": WebsocketMessageStatus.ERROR, "error": str(e)}), 500

@app.route('/find_circles', methods=['POST'])
async def find_circles_route():
    print("Received request to find circles.")
    files = await request.files
    file = files['file']
    print(f"Received file: {file.filename}")
    form = await request.form

    additional_data = form.to_dict()

    task_id = additional_data.get('task_id')

    print(additional_data)
    client_id = additional_data.get('socket_id')

    data = json.loads(additional_data['data'])

    # open image from pillow
    image = Image.open(file)


    try:
        if client_id in clients:
            await send_progress(clients[client_id], "Starting to process image for circles.", task_id)
    


        image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        
        #show_image(image,text="Before")

        if "image_offset" in data:
            # transform the image

            # translate
            image_offset = data["image_offset"]

            # translate the image

            # get the translation matrix

            M = np.float32([[1, 0, image_offset["x"]], [0, 1, image_offset["y"]]])

            # translate the image

            image = cv2.warpAffine(image, M, image.shape[1::-1], flags=cv2.INTER_LINEAR)
            

            print(f"Transformed image with offset: {image_offset}")

        if "image_angle" in data:
            image_angle = data["image_angle"]
            # rotate around center

            # get the center of the image

            center = (image.shape[1] // 2, image.shape[0] // 2)

            

            # get the rotation matrix

            M = cv2.getRotationMatrix2D(center, -image_angle, 1)

            # rotate the image

            image = cv2.warpAffine(image, M, image.shape[1::-1])



            print(f"Rotated image with angle: {image_angle}")


        # show image before and after

        #show_image(image,text="After")

        circle_precision_percentage = data["circle_precision_percentage"] if "circle_precision_percentage" in data and data["circle_precision_percentage"] != None else 1
        
        print(f"Circle precision percentage: {circle_precision_percentage}")

        circles = await find_circles_cv2("", data["rect"],data["rect_type"],img=image,circle_precision_percentage=circle_precision_percentage,
                                         
                                         on_progress= lambda x: send_progress(clients[client_id], x, task_id) if client_id in clients else None)

        # adjust circles by image_offset if needed

        if "image_offset" in data:
            for circle in circles:
                circle["center_x"] = circle["center_x"] - data["image_offset"]["x"]
                circle["center_y"] = circle["center_y"] - data["image_offset"]["y"]

        if "image_angle" in data:
            # rotate the circles back

            for circle in circles:
                # get the center of the image

                center = (image.shape[1] // 2, image.shape[0] // 2)

                # get the rotation matrix

                M = cv2.getRotationMatrix2D(center, image_angle, 1)

                # rotate the image

                circle["center_x"],circle["center_y"] = cv2.transform(np.array([[circle["center_x"],circle["center_y"]]]).reshape(-1,1,2), M).reshape(2)

            

        if client_id in clients:
            await send_progress(clients[client_id], "Completed processing image.", task_id)
        return jsonify({"status": WebsocketMessageStatus.COMPLETED_TASK, "data": circles})
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"status": WebsocketMessageStatus.ERROR, "error": str(e)}), 500

async def handle_websocket(websocket, path):
    client_id = ""
    try:
        async for message in websocket:
            message = json.loads(message)
            print(f"message: {message}")
            if message["command"] == "send_id":
                client_id = message["data"]
                clients[client_id] = websocket
                print(f"Client {client_id} connected.")
            #print(f"Received message from {client_id}: {message}")
    except websockets.exceptions.ConnectionClosed:
        print(f"Connection with {client_id} closed.")
        pass
    finally:
        if client_id != "":
            del clients[client_id]

start_server = websockets.serve(handle_websocket, 'localhost', 8996)


@app.before_serving
async def startup():
    loop = asyncio.get_event_loop()
    loop.create_task(start_server)

if __name__ == "__main__":
    config = Config()
    config.bind = ["localhost:5000"]  # bind to localhost on port 5000
    asyncio.run(serve(app, config))