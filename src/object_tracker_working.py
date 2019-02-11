import cv2

cam = cv2.VideoCapture(2)

max_distance = 0.1
threshold = 200
filepath_test = "../templates/hole_sqaure.png"

class TrackedObject:
    def __init__(self, contour):
        self.contour = contour
        self.position = self.x, self.y = self.find_center(contour)

    def find_center(self, contour):
        M = cv2.moments(contour)
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])

        return cX, cY

    def publish(self):
        print("x:",self.x,"y:",self.y)


class CandidatesFinder:
    def __init__(self, templates):
        self.t_files = templates
        self.templates = list()
        for t in self.t_files:
            self.templates.append(self.process_template(t))

    def filter_img(self, img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _,img = cv2.threshold(img, threshold,255, cv2.THRESH_BINARY)

        return img

    def process_template(self, filepath):
        template = cv2.imread(filepath, cv2.IMREAD_COLOR)
        template = self.filter_img(template)

        contours, _ = cv2.findContours(template, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        return contours


    def find_candidates(self, img):
        img = self.filter_img(img)
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = list()
        for tc in self.templates:
            for c in contours:
                distance = cv2.matchShapes(tc[0], c, cv2.CONTOURS_MATCH_I2,0)
                if distance < max_distance: #Schwellenwert
                    candidates.append(TrackedObject(c))

        return candidates

def visuals(tracked_objects, original):
    for o in tracked_objects:
        cv2.circle(original, o.position, 7, (0,0,255), -1)
        cv2.putText(original, str(o.x)+"|"+str(o.y), (o.x -20, o.y -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
        cv2.drawContours(original, o.contour, -1, (0,255,0), 2)

    cv2.imshow("Tracked Objects", original)



def main():

    finder = CandidatesFinder( [filepath_test] )

    _quit = False
    while not _quit:
        _, img = cam.read()
        original = img.copy()

        candidates = finder.find_candidates(img)
        for c in candidates:
            c.publish()

        visuals(candidates, original)

        k = cv2.waitKey(5) % 0xFF
        if k%256 == 27:
            _quit = True

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
