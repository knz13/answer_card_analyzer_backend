import argparse
import os
import random
from PIL import Image
from pdf2image import convert_from_path
import json
from find_circles import find_circles, find_circles_cv2
from opencv_python_wrapper.internal_calibrate import apply_calibration_to_image, get_calibration_center_for_image

def read_data(args):
    print("Reading data...")


def transform_data(args):
    print("Transforming data...")

def analyze_data(args):
    print("Analyzing data...")

def read_to_images(args,return_value=False,needs_calibration=True,return_as_image=False):
    print("Reading data to images...")

    if not os.path.exists("target.pdf"):
        print("Error: The target PDF file does not exist.")
        quit()

    if os.path.exists("out"):
        #remove all files
        for file in os.listdir("out"):
            os.remove(f"out/{file}")
    else:
        os.mkdir("out")
    
    # read each page of the pdf to images
        
    images = convert_from_path("target.pdf")

    image_calibration_rects = {}
    images_paths = []
    
    for i in range(len(images)):

        if return_as_image:
            images_paths.append(images[i])

            continue
        images[i].save(f"out/image_{i}.png", "PNG")

        # save calibration rect for each image

        if needs_calibration:
            center,size,rotation = get_calibration_center_for_image(f"out/image_{i}.png")
            calibration_x,calibration_y = center
            calibration_w,calibration_h = size
                
            image_calibration_rects[f"out/image_{i}.png"] = {
                "x": calibration_x,
                "y": calibration_y,
                "width": calibration_w,
                "height": calibration_h
            }

        images_paths.append(f"out/image_{i}.png")


    if not needs_calibration:
        return images_paths

    final_json = {
        "image_paths": images_paths,
        "calibration_rects": image_calibration_rects
    }

    
    if return_value:
        return final_json

    with open("output.json", "w") as file:
        json.dump(final_json, file)

        

    
def identify_circles(args):

    # try and find the identify_target.json file

    if not os.path.exists("identify_target.json"):
        print("Error: The identify_target.json file is required.")
        quit()
    
    # open the identify_target.json file
        
    with open("identify_target.json", "r") as file:
        target = json.load(file)
    
    if not "templates" in target:
        print("Error: The identify_target.json file must contain a 'templates' key.")
        quit()

    if not "target_files" in target:
        print("Error: The identify_target.json file must contain a 'target_files' key.")
        quit()
    
    if not "target_template_id" in target:
        print("Error: The identify_target.json file must contain a 'target_template_id' key.")
        quit()
    
    target_template_id = target["target_template_id"]
    templates = target["templates"]
    target_files = target["target_files"]
    

    print("LOG: Opening templates file...")

    with open(templates, "r") as file:
        templates = json.load(file)

    print("LOG: Templates file opened.")

    target_template = None

    print("LOG: Looking for target template...")

    for template in templates:
        if template["id"] == target_template_id:
            target_template = template
            break

    
    
    if not target_template:
        print(f"Error: Template with ID {target_template_id} not found.")
        quit()

    print("LOG: Target template found.")

    # look for image with template ID
        
    if type(target_files) != type([]):
        print("Error: target_files must be a list of file paths.")
        quit()

    random.shuffle(target_files)
    
    for file in target_files:
        if file.endswith(".pdf"):
            print("LOG: Reading PDF to images...")
            # write to target.pdf

            with open("target.pdf", "wb") as f:
                f.write(open(file, "rb").read())

            file_pages = read_to_images(args,return_value=True,needs_calibration=False,return_as_image=True)
            


            for page in file_pages:
                for box in target_template["boxes"]:

                    box = {
                        "x": (box["x"] + target_template["calibration_rect"]["x"]) / target_template["image_size"]["width"],
                        "y": (box["y"] +  target_template["calibration_rect"]["y"]) / target_template["image_size"]["height"],
                        "width": box["width"] / target_template["image_size"]["width"],
                        "height": box["height"]/ target_template["image_size"]["height"]
                    }
                
                    target_template_rect_percent_x = target_template["calibration_rect"]["x"] / target_template["image_size"]["width"]
                    target_template_rect_percent_y = target_template["calibration_rect"]["y"] / target_template["image_size"]["height"]

                    print(f"Page width: {page.width}, Page height: {page.height}")
                    
                    page,page_calibration_center = apply_calibration_to_image(page, target_template["calibration_rect"])
                    
                    print(f"page calibration center percent x: {page_calibration_center[0]/page.width}, page calibration center percent y: {page_calibration_center[1]/page.height}")
                    print(f"target template rect percent x: {target_template_rect_percent_x}, target template rect percent y: {target_template_rect_percent_y}")

                    # adjust box to compensate for different calibration rect

                    box["x"] = box["x"] + (page_calibration_center[0]/page.width - target_template_rect_percent_x)
                    box["y"] = box["y"] + (page_calibration_center[1]/page.height - target_template_rect_percent_y)
                    
                    circles = find_circles(page, box)

            print("LOG: PDF read to images.")
    


    """ final_json = {}

    
    circles_found = {}

    for box in boxes:

        box_without_name = {k: v for k, v in box.items() if k in ["x","y","width","height"]}

        circles = find_circles_cv2(f"{template_images}/{target_image}", box_without_name)

        circles_found[box["name"]] = circles
    

    final_json["circles"] = circles_found
    

    # save circles to file
    
    with open("output.json", "w") as file:
        json.dump(final_json, file)     """

    
def get_calibration(args):

    if not os.path.exists("identify_target.json"):
        print("Error: The identify_target.json file is required.")
        quit()
    
    # open the identify_target.json file
        
    with open("identify_target.json", "r") as file:
        target = json.load(file)
    
    if not "templates" in target:
        print("Error: The identify_target.json file must contain a 'templates' key.")
        quit()

    if not "template_images" in target:
        print("Error: The identify_target.json file must contain a 'template_images' key.")
        quit()
    
    if not "target_template_id" in target:
        print("Error: The identify_target.json file must contain a 'target_template_id' key.")
        quit()

    target_template_id = target["target_template_id"]
    templates = target["templates"]
    template_images = target["template_images"]


    print("LOG: Opening templates file...")

    with open(templates, "r") as file:
        templates = json.load(file)

    print("LOG: Templates file opened.")

    target_template = None

    print("LOG: Looking for target template...")

    for template in templates:
        if template["id"] == target_template_id:
            target_template = template
            break

    
    
    if not target_template:
        print(f"Error: Template with ID {target_template_id} not found.")
        quit()

    print("LOG: Target template found.")

    # look for image with template ID
        
    target_image = None

    print("LOG: Looking for target image...")
        
    for file in os.listdir(template_images):
        if file == f"{target_template_id}.png":
            target_image = file
            break

    if not target_image:
        print(f"Error: Image with template ID {target_template_id} not found.")
        quit()

    final_json = {}
    final_json["calibration"] = {}

    center,size,rotation = get_calibration_center_for_image(f"{template_images}/{target_image}")
    calibration_x,calibration_y = center
    calibration_w,calibration_h = size


    final_json["calibration"]["x"] = calibration_x
    final_json["calibration"]["y"] = calibration_y
    final_json["calibration"]["width"] = calibration_w
    final_json["calibration"]["height"] = calibration_h

    with open("output.json", "w") as file:
        json.dump(final_json, file)

def main():
    parser = argparse.ArgumentParser(description="A command-line tool for data operations.")
    parser.add_argument("command", choices=["read","read_to_images", "transform", "analyze","identify_circles","get_calibration"], help="Command to execute.")

    args = parser.parse_args()

    if args.command == "read":
        read_data(args)
    elif args.command == "transform":
        transform_data(args)
    elif args.command == "analyze":
        analyze_data(args)
    elif args.command == "read_to_images":
        read_to_images(args)
    elif args.command == "identify_circles":
        identify_circles(args)
    elif args.command == "get_calibration":
        get_calibration(args)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()

if __name__ == "__main__":
    main()
