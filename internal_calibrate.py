import cv2 as cv2
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from pdf2image import convert_from_path


def apply_calibration_to_image(img: Image,calibration_rect):
    # Load the image
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # draw before

    print(calibration_rect)
    

    center, size, angle = calibration_rect
    center, size = tuple(map(int, center)), tuple(map(int, size))
    
    if angle < -45:
        show_image(img)


    if angle < -45:
        angle += 90
        size = (size[1], size[0])
    elif angle > 45:
        angle -= 90
        size = (size[1], size[0])

    # Get rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    # Perform the rotation on the entire image
    rotated = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_CUBIC)

    if angle < -45:
        show_image(rotated)
    
    # Get the bounding box of the rotated rectangle
    x = int(center[0] - size[0]/2)
    y = int(center[1] - size[1]/2)
    
    # Crop the rotated image to size
    cropped = rotated[y:y+int(size[1]), x:x+int(size[0])]
    # rotate the image

    
    if angle < -45:
        show_image(cropped)

    img = cropped

    # convert to pil
    
    img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    return img


def show_image(image):
    cv2.imshow("image", image)

    # Wait until 'q' is pressed

    while True:
        # cv2.waitKey() returns the code of the pressed key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


def get_calibration_rect_for_image(img_path,img=None):

    if img is None:
        img = cv2.imread(img_path,cv2.IMREAD_GRAYSCALE)
    else:
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    
    iw, ih = img.shape[:2]

    # blur a little bit

    img = cv2.GaussianBlur(img, (43, 43), 1)

    #show_image(img)


    ret, thresh = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY_INV)
    

    cntrs, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bounding_rects = [cv2.boundingRect(cnt) for cnt in cntrs]
    iw, ih = img.shape[1], img.shape[0]  # Image width and height

    if not bounding_rects:
        return None

    # Compute center of the image
    center_x, center_y = iw / 2, ih / 2

    # Compute distances from the center for each rectangle
    rect_distances = [(rect, np.hypot(center_x - (rect[0] + rect[2] / 2), center_y - (rect[1] + rect[3] / 2))) for rect in bounding_rects]

    # Sort rectangles based on the distance in descending order
    sorted_rects = sorted(rect_distances, key=lambda x: x[1], reverse=True)

    # Selecting rectangles ensuring they are spaced apart
    selected_rects = []
    min_distance = iw * 0.1  # Minimum distance between selected rectangles, adjust as necessary

    for rect, dist in sorted_rects:
        if all(np.hypot(rect[0] + rect[2]/2 - other_rect[0] - other_rect[2]/2, rect[1] + rect[3]/2 - other_rect[1] - other_rect[3]/2) > min_distance for other_rect, _ in selected_rects):
            selected_rects.append((rect, dist))
            if len(selected_rects) == 3:
                break  # Only need the top three

    # Optionally draw these rectangles
    for rect, dist in selected_rects:
        x, y, w, h = rect
        #cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)

    

    # Assuming we got exactly three squares
    points = [(x + w // 2, y + h // 2) for (x, y, w, h),_ in selected_rects]  # Center points of squares

    # Find the furthest pair (diagonal points)
    max_distance = 0
    diagonal_pair = None
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            distance = np.hypot(points[i][0] - points[j][0], points[i][1] - points[j][1])
            if distance > max_distance:
                max_distance = distance
                diagonal_pair = (points[i], points[j])

    # The remaining point is the one not in diagonal_pair
    remaining_point = next(p for p in points if p not in diagonal_pair)

    # Calculate the fourth point using vector addition
    fourth_point = (diagonal_pair[0][0] + diagonal_pair[1][0] - remaining_point[0],
                    diagonal_pair[0][1] + diagonal_pair[1][1] - remaining_point[1])

    
    print(fourth_point)
    # draw fourth point

    cv2.circle(img, fourth_point, 10, (0, 0, 255), -1)



    # Combine all points including the predicted one
    all_points = np.array(points + [fourth_point], dtype=np.float32)
    
    rect = cv2.minAreaRect(all_points)
    

    #cv2.putText(img, str(rect[1]), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    #cv2.putText(img, "w: " + str(iw), (0, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 2)
    #cv2.putText(img, "h: " + str(ih), (0, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 2)

    rect_x, rect_y = rect[0]
    rect_w, rect_h = rect[1]

    rect_w = rect_w * 1.05
    rect_h = rect_h * 1.05


    rect = ((rect_x, rect_y), (rect_w, rect_h), rect[2])

    print(rect)

    print(all_points)

    print(img.shape)

    box = cv2.boxPoints(rect)
    box = np.int0(box)
    cv2.drawContours(img, [box], 0, (0, 0, 255), 2)

    #show_image(img)


    
    
    return rect


# show image with open cv2

def get_calibration_center_for_image(image_path,img=None):

    print("Getting calibration center for image...")

    if img is None:
        # Load the image in grayscale
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    img_shape = img.shape

    return (float(0), float(0))

    width_ratio = 2048 / img_shape[1] 

    img = cv2.resize(img, fx=width_ratio, fy=width_ratio, dsize=(0,0))
    
    _, thresholded = cv2.threshold(img, 50, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Assume the bottom-right corner of the image to search for the square
    height, width = img.shape
    closest_square = None
    min_distance_to_corner = float('inf')

    # Check each contour
    for contour in contours:
        # Approximate the contour to a polygon
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
            
        # Check if the contour is a square
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            aspect_ratio = w / float(h)
            if 0.9 < aspect_ratio < 1.1:  # Aspect ratio close to one for squares
                # Calculate the distance to the bottom-right corner
                distance_to_corner = np.sqrt((width - (x + w))**2 + (height - (y + h))**2)
                if distance_to_corner < min_distance_to_corner:
                    min_distance_to_corner = distance_to_corner
                    closest_square = (x, y, w, h)
    
    height, width = img_shape

    if closest_square:
        
        # adjust the center to the original image size

        closest_square = (closest_square[0] / width_ratio, closest_square[1] / width_ratio, closest_square[2] / width_ratio, closest_square[3] / width_ratio)



        print(f"Closest square to the bottom-right corner: {closest_square}")
        print(f"Image shape: {width}, {height}")

        # Return the position and size of the closest square to the bottom-right corner
        return (closest_square[0] + closest_square[2] / 2, closest_square[1] + closest_square[3] / 2)
    else:
        print("No black square found in the bottom-right corner.")
        return (width,height)

if __name__ == "__main__":
    """ center = get_calibration_center_for_image("examples/template_images/C2B97781C65DFAD1D9EF81581ED245D0.png")

    # draw the calibration rect

    image = cv2.imread("examples/template_images/C2B97781C65DFAD1D9EF81581ED245D0.png")

    cv2.rectangle(image, (int(center[0] - 10), int(center[1] - 10)), (int(center[0] + 10), int(center[1] + 10)), (0, 255, 0), 20)

    show_image(image) """


    images = convert_from_path("examples/target_examples/Marianna Dias.pdf")

    image = images[0]
    
    center_2 = get_calibration_center_for_image("examples/template_images/1.png",img=cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY))

    # draw the calibration rect

    image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    cv2.rectangle(image, (int(center_2[0] - 10), int(center_2[1] - 10)), (int(center_2[0] + 10), int(center_2[1] + 10)), (0, 255, 0), 20)

    show_image(image)
