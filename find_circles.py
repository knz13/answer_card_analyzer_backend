
import random
from PIL import Image
import cv2
import numpy as np
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

async def find_circles_cv2(image_path, rectangle,rectangle_type,img=None,on_progress=None,circle_size=None,circle_precision_percentage=1):
    # Load the image

    print(rectangle)

    if img is None:

        img = cv2.imread(image_path)



    # make image 512 width

    image_new_width = 4000

    width_ratio = image_new_width / img.shape[1]

    if on_progress != None:
        await on_progress(f"Resizing image to width {image_new_width}")

    img = cv2.resize(img,fx=width_ratio,fy=width_ratio,dsize=(0,0))

    old_x, old_y,width,height = rectangle.values()
    
    if old_x > 1 or old_y > 1 or width > 1 or height > 1 or old_x < 0 or old_y < 0 or width < 0 or height < 0:
        raise ValueError("The rectangle values must be between 0 and 1.")

    # transform to absolute
        
    x = int(old_x * img.shape[1])
    y = int(old_y * img.shape[0])
    width = int(width * img.shape[1])
    height = int(height * img.shape[0])

    # draw rectangle on image

    #cv2.rectangle(img, (x, y), (x + width, y + height), (0, 255, 0), 20)    

    # show image

    # crop image on rectangle

    crop_img = img[y:y+height, x:x+width]

    #show_image(crop_img)

    # add some blur

    crop_img = cv2.GaussianBlur(crop_img, (33, 33), 2.8)


    # Convert cropped image to gray scale
    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)

   # _, gray = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)

    min_dist = 70
    min_radius = 24
    max_radius = 32

    if circle_size != None:
        # circle size is a percentage of width of the image
        
        circle_size = circle_size * width

        min_radius = int(circle_size * 0.8)
        max_radius = int(circle_size * 1.2)
        min_dist = int(circle_size * 2.2)



    if on_progress != None:
        await on_progress(f"Finding circles in image...")
    
    # Apply Hough Circle Transformation to find circles
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1.6, min_dist, param1=70 * circle_precision_percentage, param2=25, minRadius=min_radius, maxRadius=max_radius)
    

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

            if np.mean(circle_cropped) < 180:
                filled = True
                cv2.circle(crop_img, (i[0], i[1]), i[2], (255, 0, 0), 2)
            else:
                filled = False
                cv2.circle(crop_img, (i[0], i[1]), i[2], (0, 255, 0), 2)

            # draw the mean on crop_img in the center of the circle

            #cv2.putText(crop_img, str(int(np.mean(circle_cropped))), (i[0], i[1]), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)








            #print(f"Text in circle: {output_circles[-1]['text']}")

            #Draw the outer circle
            # Draw the center of the circle
            cv2.circle(crop_img, (i[0], i[1]), 2, (0, 0, 255), 3)

            # show circle cropped

            #cv2.imshow("cropped",circle_cropped)

            #while True:
            #    # cv2.waitKey() returns the code of the pressed key
            #    if cv2.waitKey(1) & 0xFF == ord('q'):
            #        break 

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
            print(i)


            
    
    # now filter circles that are too close to each other

    if on_progress != None:
        await on_progress(f"Filtering circles that are too close to each other.")


    # Display the resulting frame
    #cv2.imshow('Detected circles',crop_img )
    #while True:
    #    # cv2.waitKey() returns the code of the pressed key
    #    if cv2.waitKey(1) & 0xFF == ord('q'):
    #        break 
    #cv2.destroyAllWindows()
    
    return output_circles
