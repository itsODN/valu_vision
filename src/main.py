import numpy as np
import cv2
import imutils
from matplotlib import pyplot as plt

cam = cv2.VideoCapture(2)


def take_img(cam):
    ret, frame = cam.read()
    #cv2.imwrite("test.png", frame)
    cam.release()
    return frame

def show_img(img):
    cv2.imshow("test", img)
    cv2.waitKey(0)

def get_centers(img_o, img_m,visual=False):
    contours, hierarchy = cv2.findContours(img_m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    #contours = imutils.grab_contours(contours)

    center_pos = list()

    for c in contours:
        M = cv2.moments(c)
        try:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
        except ZeroDivisionError:
            continue

        if visual:
            cv2.drawContours(img_o, [c], -1, (0,255,0), 2)
            cv2.circle(img_o, (cX,cY), 7, (0,0,255), -1)
            cv2.putText(img_o, str(cX)+"|"+str(cY), (cX -20, cY -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
            cv2.imshow("centers", img_o)
            cv2.waitKey(0)

        center_pos.append( (cX,cY) )

    return center_pos

def show_contour(img, contours):
    print(contours)
    contours = contours[0].reshape(-1,2)

    for (x,y) in contours:
        cv2.circle(img, (x,y), 1, (255,0,0), 3)

def filter_stack(img):
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = cv2.GaussianBlur(img, (5,5), 0)
    ret, img = cv2.threshold(img, 127,255,0)
    #img = cv2.Canny(img,100,100)

    return img

def match_template(img):
    img_rgb = img
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)
    template = cv2.imread('../templates/hole_sqaure.png',0)
    w, h = template.shape[::-1]

    res = cv2.matchTemplate(img_gray,template,cv2.TM_CCOEFF_NORMED)
    threshold = 0.8
    loc = np.where( res >= threshold)
    for pt in zip(*loc[::-1]):
        cv2.rectangle(img_rgb, pt, (pt[0] + w, pt[1] + h), (0,0,255), 2)

    cv2.imshow('template matching',img_rgb)
    cv2.waitKey(0)



def main():
    img = take_img(cam)
    #cv2.imwrite("../templates/hole_sqaure.png",img)

    img2 = filter_stack(img)

    match_template(img)

    center_pos = get_centers(img, img2,visual=False)
    print(center_pos)




    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
