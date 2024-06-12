
import random
from PIL import Image
import cv2
import numpy as np
from utils import Utils
from websocket_types import BoxRectangleType

def replace_all_not_used(text):
    text = "".join(list(filter(lambda x: (x in [str(i) for i in range(10)]) or (x in [chr(i) for i in range(65,91)]),list(text))))
    
    return text


def show_image(image,text="image"):
    cv2.imshow(text, image)

    # Wait until 'q' is pressed

    while True:
        # cv2.waitKey() returns the code of the pressed key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cv2.destroyAllWindows()



def distance_between_points(point1, point2):
    return ((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)/2




async def find_circles(img, rectangle,rectangle_type,on_progress=None):
    
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    return await find_circles_cv2(img, rectangle,rectangle_type,img=img,on_progress=on_progress)



async def find_circles_cv2(image_path, rectangle,rectangle_type,param2,dp,darkness_threshold = 180/255,img=None,on_progress=None,circle_size=None,circle_precision_percentage=1):
    # Load the image

    Utils.log_info(f"Got circle size: {circle_size}")

    if img is None:

        img = cv2.imread(image_path)

    #show_image(img)

    # make image 512 width

    image_new_width = 4000

    width_ratio = image_new_width / img.shape[1]

    img = cv2.resize(img,fx=width_ratio,fy=width_ratio,dsize=(0,0))

    old_x, old_y,width,height = rectangle.values()
    
    if old_x > 1 or old_y > 1 or width > 1 or height > 1 or old_x < 0 or old_y < 0 or width < 0 or height < 0:
        raise ValueError("The rectangle values must be between 0 and 1.")

    # transform to absolute
        
    x = int(old_x * img.shape[1])
    y = int(old_y * img.shape[0])
    width = int(width * img.shape[1])
    height = int(height * img.shape[0])

    if Utils.is_debug():

        # draw rectangle on image

        cv2.rectangle(img, (x, y), (x + width, y + height), (0, 255, 0), 20)    

    # show image

    # crop image on rectangle

    crop_img = img[y:y+height, x:x+width]

    #show_image(crop_img)

    # add some blur

    crop_img = cv2.GaussianBlur(crop_img, (17, 17), 1.5)

    #show_image(crop_img)

    # Convert cropped image to gray scale
    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)

   # _, gray = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)

    min_dist = 68
    min_radius = 34
    max_radius = 39

    if circle_size != None:
        # circle size is a percentage of width of the image
        
        circle_size = circle_size * img.shape[1]

        min_radius = int(circle_size * 1)
        max_radius = int(circle_size * 1.15)
        min_dist = int(circle_size * 1.8)

        Utils.log_info(f"Circle size: {circle_size} | min_radius: {min_radius} | max_radius: {max_radius} | min_dist: {min_dist}")
    


    if on_progress != None:
        await on_progress(f"Finding circles in image...")
    
    # Apply Hough Circle Transformation to find circles
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp, min_dist, param1=70 * circle_precision_percentage, param2=param2, minRadius=min_radius, maxRadius=max_radius)
    

    if circles is None:
        return []
    
    
    circles = np.uint16(np.around(circles))

    if on_progress != None:
        await on_progress(f"Found {len(circles[0])} circles in image.")

    output_circles = []
    

    for i in circles[0, :]:
        i = i.astype(int)
        y_min = max(i[1] - i[2],0)
        x_min = max(i[0]-i[2],0)
        y_max = min(i[1] + i[2],crop_img.shape[0])
        x_max = min(i[0] + i[2],crop_img.shape[1])
        
        try:

            # clamp to prevent acessing negative indices

            circle_cropped = crop_img[y_min:y_max,x_min:x_max]

            # check if filled (black) circle



            filled = False

            if np.mean(circle_cropped) < darkness_threshold * 255:
                filled = True
                if Utils.is_debug():

                    cv2.circle(crop_img, (i[0], i[1]), i[2], (255, 0, 0), 2)
            else:
                filled = False
                if Utils.is_debug():

                    cv2.circle(crop_img, (i[0], i[1]), i[2], (0, 255, 0), 2)

            # draw the mean on crop_img in the center of the circle

            if Utils.is_debug():
                cv2.putText(crop_img, str(int(np.mean(circle_cropped))), (i[0], i[1]), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)


            if Utils.is_debug():
                #Draw the outer circle
                # Draw the center of the circle
                cv2.circle(crop_img, (i[0], i[1]), 2, (0, 0, 255), 3)

                # show circle cropped

                #show_image(circle_cropped)

            # adjust circle to the original image


            i[0] = i[0] + x

            i[1] = i[1] + y

            # now use the width_ratio

            i[0] = i[0] / width_ratio

            i[1] = i[1] / width_ratio

            i[2] = i[2] / width_ratio

            output_circles.append({
                "center_x": float(i[0]),
                "center_y": float(i[1]),
                "radius": float(i[2]),
                "filled": filled,
                "id": random.randbytes(10).hex()
            })
        except Exception as e:
            Utils.log_error(i)

    # filter circles


    if circle_size != None:

        if rectangle_type == BoxRectangleType.MATRICULA:
            # find all "rows"

            Utils.log_info(f"Finding rows...")

            rows = []

            for circle in output_circles:
                found = False
                for row in rows:
                    #Utils.log_info(f"row: {row} | circle: {circle}")
                    if distance_between_points((circle["center_x"],circle["center_y"]),(row[0]["center_x"],row[0]["center_y"])) < circle_size * 1.5:
                        row.append(circle)
                        found = True
                        break
                if not found:
                    rows.append([circle])

                    #Utils.log_info(f"Current rows: {rows}")

            # sort rows by y

            rows = sorted(rows,key=lambda x: x[0]["center_y"])

            # find the most common number of circles in a row

            most_common = max(set([len(row) for row in rows]), key = [len(row) for row in rows].count)

            # filter rows with less than most_common


            circles_to_remove = []

            for row in rows:
                if abs(len(row) - most_common) > 1:
                    Utils.log_info(f"Removing row: {row}")
                    circles_to_remove = circles_to_remove + [circle["id"] for circle in row]

            output_circles = [circle for circle in output_circles if circle["id"] not in circles_to_remove]

    


            

    if Utils.is_debug():
        show_image(crop_img)


    
    return output_circles
