import asyncio
import json
from PIL import Image
import cv2
import numpy as np
import websockets
from find_circles import find_circles, find_circles_cv2, show_image
from read_to_images import read_to_images
from websocket_types import WebsocketMessageCommand, WebsocketMessageStatus



async def message_progress(websocket,message):
    print(f"Sending progress message: {message}")
    await websocket.send(json.dumps({"status": WebsocketMessageStatus.PROGRESS, "data": message}))



async def process_message(websocket, path):

    

    while True:
        try:
            message = await websocket.recv()

            print(f"Received message: {len(message)}")


            data = json.loads(message)
            command = data["command"]
            data = data["data"]

            print(f"Received command: {command}")
            print(f"Received data: {list(data.keys())}")

            if command == WebsocketMessageCommand.READ_TO_IMAGES:
                try:
                    result_json= await read_to_images(data["pdf_path"],needs_calibration=True,on_progress= lambda x: message_progress(websocket,x))
                    


                    # Implement command handling code here
                    await websocket.send(json.dumps({"status": WebsocketMessageStatus.COMPLETED_TASK, "data": result_json}))
                except Exception as e:
                    print(f"An error occurred: {e}")
                    await websocket.send(json.dumps({"status": WebsocketMessageStatus.ERROR, "error": str(e)}))

            elif command == WebsocketMessageCommand.FIND_CIRCLES:
                try:

                    image = Image.open(data["image_path"])


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

                    circles = await find_circles_cv2("", data["rect"],data["rect_type"],on_progress= lambda x: message_progress(websocket,x),img=image,circle_precision_percentage=circle_precision_percentage)

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

                    # Implement command handling code here
                    await websocket.send(json.dumps({"status": WebsocketMessageStatus.COMPLETED_TASK, "data": circles}))
                except Exception as e:
                    print(f"An error occurred: {e}")
                    await websocket.send(json.dumps({"status": WebsocketMessageStatus.ERROR, "error": str(e)}))
            elif command == WebsocketMessageCommand.IDENTIFY_CIRCLES:

                # Implement command handling code here
                await websocket.send(json.dumps({"status": "Circles identified"}))

            elif command == WebsocketMessageCommand.GET_CALIBRATION:
                # Implement command handling code here
                await websocket.send(json.dumps({"status": "Calibration received"}))

            else:
                print(f"Unknown command: {command}")
                await websocket.send(json.dumps({"error": "Unknown command"}))

        except websockets.ConnectionClosedError as e:
            print(f"Connection closed unexpectedly: {e}")
            break

        except Exception as e:
            print(f"An unexpected error occurred: {e}")

            await websocket.send(json.dumps({"error": "An unexpected error occurred"}))




start_server = websockets.serve(process_message, "localhost", 8996)

print("Server started.")

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

