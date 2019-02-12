import cv2
import paho.mqtt.client
from operator import itemgetter

class App:
    def __init__(self):

        self.setup()
        self.score_filter = SummaryScoreFilter()
        self.filter       = ImageFilter(self.settings)
        self.cam          = cv2.VideoCapture(self.settings["camera_number"])
        self.mqtt         = MQTT_Client(self)


        self.quit      = False
        self.overlay   = None
        self.payload   = None
        self.template  = None
        self.increment = 1
        self.state     = "standby"

    #---------------------------------------------------------------------------
    #Program Control Flow
    #---------------------------------------------------------------------------

    def setup(self):
        self.settings = dict()
        cast_int = ["threshold","camera_number","port"]
        cast_float = ["max_distance"]
        with open("../settings.txt","r") as file:
            for line in file:
                if line[0] == "#" or line[0] == "":
                    continue
                line = line.rstrip().split("=")
                if line[0] in cast_int:
                    self.settings[line[0]] = int(line[1])
                elif line[0] in cast_float:
                    self.settings[line[0]] = float(line[1])
                else:
                    self.settings[line[0]] = line[1]
        print(self.settings)

    def save_settings(self):
        with open("../settings.txt","w") as file:
            for key in self.settings:
                file.write(key+"="+str(self.settings[key])+"\n")

    def main_loop(self):

        while not self.quit:
            self.process_inbox()
            if self.overlay:
                self.toggle_overlay()
                self.overlay = None


            _, img = self.cam.read()



            if self.state == "standby":
                pass

            if self.state == "tracking":

                img_filtered = self.filter.apply(img)

                candidates = self.finder.find_candidates(img_filtered)

                winner = self.score_filter.update(candidates)

                if winner:
                    print("Publishing:",winner)
                    self.mqtt.publish(winner)


    def shutdown(self):
        print("quitting...")
        self.quit = True
        self.cam.release()
        cv2.destroyAllWindows()
        quit()

    def toggle_overlay(self):
        if self.overlay == "filter_settings":
            self.adjust_filter_settings()
        if self.overlay == "finder_settings":
            self.adjust_finder_settings()
        return

    #---------------------------------------------------------------------------
    # communication
    #---------------------------------------------------------------------------
    def publish_positions(self, objs):
        msg = list()
        if objs:
            for obj in objs:
                msg.append(str(obj.x)+","+str(obj.y))

        self.mqtt.publish(";".join(msg))

    def receive(self, msg):
        self.payload = str(msg)[2:-1].split(";")
        return

    def process_inbox(self):
        self.mqtt.update()
        if self.payload:
            if self.payload[0] == "quit":
                self.shutdown()
            elif self.payload[0] == "stop_tracking" and self.state == "tracking":
                cv2.destroyAllWindows()
                self.state = "standby"
                print("Stoping Tracking. On standby...")
                del self.finder
            elif self.payload[0] == "new_template" and self.state == "standby":
                cv2.destroyAllWindows()
                print("Received new Template. Changing to tracking mode")
                self.new_template(self.payload[1])
                self.state = "tracking"

            if self.payload[0] == "overlay" and not self.overlay:
                self.overlay = self.payload[1]

            self.payload = None

    #---------------------------------------------------------------------------
    # Image Processing
    #---------------------------------------------------------------------------

    def new_template(self, file_name):
        filepath = self.settings["template_filepath"] + file_name
        img = cv2.imread(filepath, cv2.IMREAD_COLOR)
        img = self.filter.apply(img)
        self.finder = BinaryFinder(img, self.settings)


    def draw_contour(self, tracked_objects, img):
        for o in tracked_objects:
            cv2.circle(img, o.position, 7, (0,0,255), -1)
            cv2.putText(img, str(o.x)+"|"+str(o.y), (o.x -20, o.y -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
            cv2.drawContours(img, o.contour, -1, (0,255,0), 2)

        return img

    def adjust_filter_settings(self):
        print("Engaging filter settings mode")

        window_name = "Filter Settings"
        cv2.namedWindow(window_name)
        cv2.createTrackbar("Threshold",window_name,0,255,self.nothing)

        while True:
            self.process_inbox()
            _, img = self.cam.read()
            quit = self.key_events()
            if quit:
                break

            threshold = cv2.getTrackbarPos("Threshold",window_name)
            self.settings["threshold"] = threshold
            self.filter.update_settings(self.settings)

            filtered_img = self.filter.apply(img)


            cv2.imshow(window_name, filtered_img)
        cv2.destroyWindow(window_name)
        self.overlay = None

        return

    def nothing(self,x):
        pass

    def adjust_finder_settings(self):
        print("Engaging finder settings mode")

        while True:
            self.process_inbox()
            _, img = self.cam.read()
            quit = self.key_events()
            if quit:
                break


            filtered_img = self.filter.apply(img)
            candidates = self.finder.find_candidates(filtered_img)

            img = self.draw_contour(candidates, img)
            cv2.imshow(window_name,img)

        cv2.destroyAllWindows()
        self.overlay = None

        return





    def exit_key(self):
        k = cv2.waitKey(5) % 0xFF
        if k%256 == 27:
            self.quit = True
            self.shutdown()

    def key_events(self):
        k = cv2.waitKey(5) % 0xFF

        if k == ord("+"):
            self.settings["threshold"] += self.increment
            print("Threshold:",self.settings["threshold"])
            self.filter.update_settings(self.settings)
        elif k == ord("-"):
            self.settings["threshold"] -= self.increment
            print("Threshold:",self.settings["threshold"])
            self.filter.update_settings(self.settings)

        if k == ord("*"):
            #global threshold
            self.increment += 1
            print("Increment:",self.increment)
        elif k == ord("/"):
            if self.increment == 1:
                pass
            else:
                self.increment -= 1
            print("Increment:",self.increment)

        if k == ord("s"):
            self.save_settings()

        if k == ord("q"):
            return True


class MQTT_Client:
    def __init__(self, app):
        self.master = app
        self.client = paho.mqtt.client.Client()

        self.input_topic  = app.settings["input_topic"]
        self.output_topic = app.settings["output_topic"]

        self.client.on_message    = self.on_message
        self.client.on_subscribe  = self.on_subscribe
        self.client.on_disconnect = self.on_disconnect


        self.client.connect(app.settings["broker"], app.settings["port"], 60)
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

    def __repr__(self):
        return "[Tracked Object|"+str(self.x)+":"+str(self.y)+";"+str(self.persistence)+"]"

    def __str__(self):
        return str(self.x)+","+str(self.y)

    def find_center(self, contour):
        M = cv2.moments(contour)
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])

        return cX, cY

    def publish(self):
        print("x:",self.x,"y:",self.y)

class ImageFilter:
    def __init__(self, settings, mode="binary"):
        self.settings = settings
        self.mode = mode

    def apply(self, img):
        if self.mode == "binary":
            img = self.binary(img)
            return img

    def update_settings(self, settings):
        self.settings = settings

    def binary(self, img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _,img = cv2.threshold(img, self.settings["threshold"],255, cv2.THRESH_BINARY)

        return img


class SummaryScoreFilter:
    def __init__(self):
        self.tracked_objects = list()
        self.cycles = 5
        self.counter = 0

    def cycle_control(self):
        if self.counter >= self.cycles:
            winner = self.select_best()
            self.counter = 0
            return winner

        else:
            self.counter += 1

    def update(self, candidates):
        self.tracked_objects.append(candidates)

        return self.cycle_control()

    def select_best(self):
        max_ocurance = 0
        summary = dict()
        for round in self.tracked_objects:
            for obj in round:
                if str(obj) in summary:
                    summary[str(obj)][0] += 1
                    summary[str(obj)][1].append(obj.distance)
                else:
                    summary[str(obj)] = [1,[obj.distance]]

        # Filter out everything with lower occurance than max occurance
        for k in summary:
            if summary[k][0] > max_ocurance:
                max_ocurance = summary[k][0]
        summary = {k:v for k, v in summary.items() if v[0] == max_ocurance}

        # Average of distances, select smallest distance
        for k in summary:
            summary[k][1] = sum(summary[k][1]) / len(summary[k][1])
        winner = [k for k in sorted(summary, key=summary.get(1), reverse=True)][0]

        return winner
        #print(summary,"\n")
        self.tracked_objects = list()

class BinaryFinder:
    def __init__(self, template_img, settings):
        self.settings = settings
        self.template_contour,_ = cv2.findContours(template_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    def process_template(self, filepath):
        template = cv2.imread(filepath, cv2.IMREAD_COLOR)
        template = self.filter_img(template)

        contours, _ = cv2.findContours(template, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        return contours

    def update_settings(self, settings):
        self.settings = settings


    def find_candidates(self, img):
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = list()

        for c in contours:
            distance = cv2.matchShapes(self.template_contour[0], c, cv2.CONTOURS_MATCH_I2,0)
            if distance < self.settings["max_distance"]: #Schwellenwert
                candidates.append(TrackedObject(c, distance))

        return candidates




if __name__ == "__main__":
    App().main_loop()
