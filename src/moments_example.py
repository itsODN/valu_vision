import cv2
from math import copysign, log10

def take_img():
    cam = cv2.VideoCapture(2)
    ret, frame = cam.read()
    #cv2.imwrite("test.png", frame)
    cam.release()

    return frame


def get_huMoments(img):


    # Calculate Moments
    moments = cv2.moments(img)
    hu_moments = cv2.HuMoments(moments)

    # Transform Hu so they're in the same range
    for i in range(0,7):
        hu_moments[i] = -1 * copysign(1.0, hu_moments[i]) * log10(abs(hu_moments[i]))

    return hu_moments


def main():
    threshold = 200

    template = cv2.imread("../templates/hole_sqaure.png",0)
    _,template = cv2.threshold(template, threshold,255, cv2.THRESH_BINARY)

    cv2.imshow("template", template)
    cv2.waitKey(0)


    img = take_img()
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _,img = cv2.threshold(img, threshold,255, cv2.THRESH_BINARY)

    cv2.imshow("image", img)
    cv2.waitKey(0)

    template_hu = get_huMoments(template)
    img_hu = get_huMoments(img)

    d1 = cv2.matchShapes(template, img, cv2.CONTOURS_MATCH_I1,0)
    d2 = cv2.matchShapes(template, img, cv2.CONTOURS_MATCH_I2,0)
    d3 = cv2.matchShapes(template, img, cv2.CONTOURS_MATCH_I3,0)

    print("d1:",d1)
    print("d2:",d2)
    print("d3:",d3)

if __name__ == "__main__":
    main()
