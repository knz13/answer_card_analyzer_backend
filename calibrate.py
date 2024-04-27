

import random
from PIL import Image
import cv2
import imagehash
import numpy as np
from find_circles import show_image
from websocket_types import BoxRectangleType


def get_calibration_rect_for_image(img_path):

    img = cv2.imread(img_path)
    
    iw, ih = img.shape[:2]
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV)
    
    cntrs, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    def draw_squares(img, cntrs):
        for cntr in cntrs:
            x, y, w, h = cv2.boundingRect(cntr)

            area = cv2.contourArea(cntr)

            cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(img, f"{x} {y}", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    # draw_squares(img, cntrs)
    # plt.imshow(img)
    # plt.show()

    guiding_squares = []
    cntr_area = [(cntr, cv2.contourArea(cntr)) for cntr in cntrs]
    sorted_cntrs = sorted(cntr_area, key=lambda x: x[1], reverse=True)
    for i in range(len(sorted_cntrs) - 6):
        window = sorted_cntrs[i:i+6]
        areas = [x[1] for x in window]
        if max(areas) / min(areas) < 1.1:
            guiding_squares = window
            break

    #draw_squares(img, [x[0] for x in guiding_squares])
    squares_points = np.array([(x, y) for (x, y, w, h) in [cv2.boundingRect(x[0]) for x in guiding_squares]])
    rect = cv2.minAreaRect(squares_points)
    box = cv2.boxPoints(rect)
    box = np.int0(box)
    #cv2.drawContours(img, [box], 0, (0, 0, 255), 2)

    #cv2.putText(img, str(rect[1]), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    #cv2.putText(img, "w: " + str(iw), (0, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 2)
    #cv2.putText(img, "h: " + str(ih), (0, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 2)

    

    rect_w, rect_h = rect[1]
    rect_x, rect_y = rect[0]
    #print("rect_w: " + str(rect_w))
    #print("rect_h: " + str(rect_h))
    #print("rect_x: " + str(rect_x))
    #print("rect_y: " + str(rect_y))
    #print("iw: " + str(iw))
    #print("ih: " + str(ih))
    #print("square_area: " + str(guiding_squares[0][1]))

    # show image cv2

    show_image(img)
    
    return rect_x, rect_y, rect_w, rect_h
