import cv2
import os
from pdf2image import convert_from_path
import json


def correct_skew_and_draw_contour(image_path):
    # Load the image
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Assuming the largest contour corresponds to the entire page
    largest_contour = max(contours, key=cv2.contourArea)
    
    # Draw the largest contour on the image
    cv2.drawContours(image, [largest_contour], -1, (0, 255, 0), 3)  # Green contour

    # Save the image with the contour
    cv2.imwrite('image_with_largest_contour.png', image)

# first read the file if it exists

file_name = "directions.json"

if os.path.exists(file_name):
    with open(file_name, "r") as file:
        data = json.loads(file.read())

    if "location" not in data:
        print("location not found in directions.json")

        quit()
    
    location = data["location"]

    # extract the image

    images = convert_from_path(location)

    if not os.path.exists("temp"):
        os.mkdir("temp")

    # save the images
    
    for i in range(len(images)):
        images[i].save(f"temp/image_{i}.png", "PNG")

        correct_skew_and_draw_contour(f"temp/image_{i}.png")

        quit()

else:
    print("directions.json does not exist.")

