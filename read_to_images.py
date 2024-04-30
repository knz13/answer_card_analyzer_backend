
import argparse
import io
import os
import random
from PIL import Image
from pdf2image import convert_from_path,convert_from_bytes
import json
from find_circles import find_circles, find_circles_cv2
from internal_calibrate import apply_calibration_to_image, get_calibration_center_for_image,get_calibration_rect_for_image
from fastapi import UploadFile


async def read_to_images(file: UploadFile,needs_calibration=True,on_progress=None):
    print("Reading data to images...")

    # read each page of the pdf to images

    bytes_arr = await file.read()

    if file.filename.endswith(".pdf"):

        if on_progress != None: 
            await on_progress(f"Converting PDF to images...")

        
        
        images = convert_from_bytes(bytes_arr,thread_count=4)
        
        if on_progress != None: 
            await on_progress(f"Converted PDF, {len(images)} pages")

    else:
        images = [Image.open(bytes_arr)]
        if on_progress != None: 
            await on_progress(f"Read image")

    images_paths = []
    final_json = {
        "images": {},
        "image_calibration_rects": {},
        "image_sizes": {}
    }
    
    for i in range(len(images)):

        if on_progress != None: 
                await on_progress(f"Saving image {i} to temporary directory.")
    

        randomHash = random.randbytes(8).hex()

        image_path = os.path.abspath(f"out/image_{randomHash}.png")

        # resize image to 2000 width if its width is greater than 2000

        if images[i].width > 1500:
            width_ratio = 1500 / images[i].width
            images[i] = images[i].resize((int(images[i].width * width_ratio), int(images[i].height * width_ratio)))

        #images[i].save(image_path, "PNG")

        # crop and rotate to straighten and then save
        if needs_calibration:

            calibration_rect = get_calibration_rect_for_image(image_path,img=images[i])
            if on_progress != None: 
                await on_progress(f"Applying calibration to image {i}")

            print(f"Calibration rect: {calibration_rect}")
            print(f"Image size: {images[i].width}, {images[i].height}")


            img=  apply_calibration_to_image(images[i], calibration_rect)

            #img.save(image_path, "PNG")

            if on_progress != None: 
                await on_progress(f"Applied calibration to image {i}")

          

            final_json["image_calibration_rects"][randomHash] = {
                "x": float(0),
                "y": float(0)
            }

        
        
        final_json["images"][randomHash] = img
        final_json["image_sizes"][randomHash] = {
            "width": float(img.width),
            "height": float(img.height)
            
        }



    if not needs_calibration:
        return images_paths

    
    return final_json

        
