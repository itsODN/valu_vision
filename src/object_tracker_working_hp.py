import cv2
import paho.mqtt.client


max_distance = 0.2
threshold = 200
filepath_test = "../templates/hole_sqaure.png"


class App:
    def __init__(self):
        self.finder = CandidatesFinder( [filepath_test] )
        self.tracker = TrackingMaster()
        self.cam = cv2.VideoCapture(2)
        self.mqtt = MQTT_Client(self)

        self.quit = False
        self.payload = None

    def main_loop(self):

        while not self.quit:
            self.mqtt.update()

            _, img = self.cam.read()
            original = img.copy()

            candidates = self.finder.find_candidates(img)
            self.tracker.process_candidates(candidates)
            objs = self.tracker.update()
            self.publish_positions(objs)

            self.visuals(objs, original)

            k = cv2.waitKey(5) % 0xFF
            if k%256 == 27:
                self.quit = True

        self.cam.release()
        cv2.destroyAllWindows()

    def publish_positions(self, objs):
        msg = list()
        if objs:
            for obj in objs:
                msg.append(str(obj.x)+","+str(obj.y))

        self.mqtt.publish(";".join(msg))

    def receive(self, msg):
        self.payload = str(msg)[2:-1].split(";")
        return

    def check_payload(self):
        if self.payload:
            print(self.payload)
            self.payload = None

    def visuals(self, tracked_objects, original):
        for o in tracked_objects:
            cv2.circle(original, o.position, 7, (0,0,255), -1)
            cv2.putText(original, str(o.x)+"|"+str(o.y), (o.x -20, o.y -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
            cv2.drawContours(original, o.contour, -1, (0,255,0), 2)

        cv2.imshow("Tracked Objects", original)

class MQTT_Client:
    def __init__(self, app):
        self.master = app
        self.client = paho.mqtt.client.Client()

        self.input_topic  = "iot/data/ssfcic/camera_tracking/commands"
        self.output_topic = "iot/data/ssfcic/camera_tracking/position"

        self.client.on_message    = self.on_message
        self.client.on_subscribe  = self.on_subscribe
        self.client.on_disconnect = self.on_disconnect


        self.client.connect("iot.eclipse.org", 1883, 60)
        self.client.subscribe(self.input_topic)
        print("MQTT client initiated")

    def on_disconnect(self, client, userdata, rc):
        print("disconnected")
        self.client.reconnect()

    def on_message(self, client, userdata, msg):
        self.master.receive(msg.payload)

    def on_subscribe(self, client, userdata, mid, granted_qos):
        print("Subscribed to:", client, userdata, mid, granted_qos)

    def update(self):
        self.client.loop(0.1)

    def publish(self, msg):
        self.client.publish(self.output_topic, str(msg))

class TrackedObject:
    def __init__(self, contour, distance):
        self.contour = contour
        self.distance = distance
        self.position = self.x, self.y = self.find_center(contour)
        self.persistence = 2
        self.new = True


    def __repr__(self):
        return "[Tracked Object|"+str(self.x)+":"+str(self.y)+";"+str(self.persistence)+"]"

    def find_center(self, contour):
        M = cv2.moments(contour)
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])

        return cX, cY

    def publish(self):
        print("x:",self.x,"y:",self.y)

class TrackingMaster:
    def __init__(self):
        self.tracked_objects = list()
        self.watched_objects = list()
        self.watch_index = list()

        self.max_score   = 8
        self.found_score = 3
        self.lost_score  = -2

    def add_to_watchlist(self,obj):
        self.watched_objects.append(obj)
        self.watch_index.append(obj.position)

    def process_candidates(self, candidates):

        # Prüfe ob kandidat in watch list ist. wenn nein füge ihn hinzu sonst score
        for c in candidates:
            if c.position in self.watch_index:
                self.increase_score(c.position)
            else:
                self.add_to_watchlist(c)


    def update(self):
        for obj in self.watched_objects:
            obj.persistence += self.lost_score
            if obj.persistence <= 0:
                self.remove_object(obj)

        print(self.watched_objects)
        return self.watched_objects

    def remove_object(self,obj):
        self.watch_index.remove(obj.position)
        self.watched_objects.remove(obj)
        del obj

    def increase_score(self, position):
        for obj in self.watched_objects:
            if position == obj.position:
                if obj.persistence > self.max_score:
                    return
                else:
                    obj.persistence += self.found_score





class CandidatesFinder:
    def __init__(self, templates):
        self.t_files = templates
        self.templates = list()
        for t in self.t_files:
            self.templates.append(self.process_template(t))

    def filter_img(self, img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _,img = cv2.threshold(img, threshold,255, cv2.THRESH_BINARY)
        cv2.imshow("grey",img)

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
                    candidates.append(TrackedObject(c, distance))

        return candidates




if __name__ == "__main__":
    App().main_loop()
