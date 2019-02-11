import cv2
from math import copysign, log10

def take_img():
    cam = cv2.VideoCapture(2)
    ret, frame = cam.read()
    #cv2.imwrite("test.png", frame)
    cam.release()

    return frame

def show_img(img):
    cv2.imshow("test", img)
    cv2.waitKey(0)

def get_huMoments(img):


    # Calculate Moments
    moments = cv2.moments(img)
    hu_moments = cv2.HuMoments(moments)

    # Transform Hu so they're in the same range
    for i in range(0,7):
        hu_moments[i] = -1 * copysign(1.0, hu_moments[i]) * log10(abs(hu_moments[i]))

    return hu_moments


def example():
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

def draw_contour(img, contours):
    cv2.drawContours(img, [contours], -1, (0,255,0), 2)


def main():
    threshold = 200

    template = cv2.imread("../templates/hole_sqaure.png",0)
    _,template = cv2.threshold(template, threshold,255, cv2.THRESH_BINARY)
    show_img(template)

    img = take_img()
    original = img.copy()
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _,img = cv2.threshold(img, threshold,255, cv2.THRESH_BINARY)
    show_img(img)

    t_contours, _ = cv2.findContours(template, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    i_contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    print(type(t_contours),t_contours)

    distances = list()
    for c in i_contours:
        distances.append(cv2.matchShapes(t_contours[0], c, cv2.CONTOURS_MATCH_I2,0))

    for i,d in enumerate(distances):
        if d < 0.1:
            print(d,"is same")
            cv2.drawContours(original, i_contours[i], -1, (0,255,0), 2)

        else:
            print(d,"is different")

    show_img(original)


if __name__ == "__main__":
    main()
