import cv2
from math import copysign, log10



def find_center(contours):
        M = cv2.moments(contours)
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])

        return cX, cY


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


matches = list()
positions = list()
def main():
    _quit = False
    threshold = 200

    cam = cv2.VideoCapture(2)

    template = cv2.imread("../templates/hole_sqaure.png",0)
    _,template = cv2.threshold(template, threshold,255, cv2.THRESH_BINARY)
    t_contours, _ = cv2.findContours(template, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    while not _quit:
        _, img = cam.read()
        original = img.copy()

        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _,img = cv2.threshold(img, threshold,255, cv2.THRESH_BINARY)

        i_contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        distances = list()
        for c in i_contours:
            distances.append(cv2.matchShapes(t_contours[0], c, cv2.CONTOURS_MATCH_I2,0))

        positions = list()
        for i,d in enumerate(distances):
            if d < 0.1: #Schwellenwert
                cX,cY = find_center(i_contours[i])
                matches.append([cX, cY, 0])
                positions.append( (cX,cY) )


        for i, m in enumerate(matches):
            for p in positions:
                if (m[0], m[1]) not in positions:
                    del matches[i]

        for j, m in enumerate(matches):

            if cX == m[0] and cY == m[1]:
                m[2] += 1

            if m[2] == 0:
                del matches[j]

            elif m[2] > 10:
                cv2.circle(original, (m[0],m[1]), 7, (0,0,255), -1)
                cv2.putText(original, str(m[0])+"|"+str(m[1]), (m[0] -20, m[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)






        cv2.imshow("Tracking", original)

        k = cv2.waitKey(5) % 0xFF
        if k%256 == 27:
            _quit = True

    cam.release()

if __name__ == "__main__":
    main()
