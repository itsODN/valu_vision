import cv2
import paho.mqtt.client
from operator import itemgetter
import numpy as np

class App:
    def __init__(self):

        self.setup()
        self.score_filter = SummaryScoreFilter()
        self.cam          = cv2.VideoCapture(self.settings["camera_number"])
        self.mqtt         = MQTT_Client(self)


        self.quit      = False
        self.overlay   = None
        self.payload   = None
        self.template  = None
        self.increment = 1
        self.state     = "standby"

        # Debugging Tools
        self.show_stream = True

    #---------------------------------------------------------------------------
    #Program Control Flow
    #---------------------------------------------------------------------------

    def setup(self):
        self.settings = dict()
        cast_int = ["camera_number","port"]
        with open("../settings.txt","r") as file:
            for line in file:
                if line[0] == "#" or line[0] == "":
                    continue
                line = line.rstrip().split("=")
                if line[0] in cast_int:
                    self.settings[line[0]] = int(line[1])
                else:
                    self.settings[line[0]] = line[1]
        print(self.settings)

    def save_settings(self):
        with open("../settings.txt","w") as file:
            for key in self.settings:
                file.write(key+"="+str(self.settings[key])+"\n")

    def main_loop(self):

        while not self.quit:
            _, img = self.cam.read()
            self.process_inbox()
            if self.overlay:
                self.toggle_overlay()
                self.overlay = None

            if self.state == "standby":
                pass

            if self.state == "tracking":

                matches = self.filter.go(img)
                for p,c,d in matches:
                    #publish here
                    pass


                if self.show_stream:
                    img = self.draw_contour(matches, img)
                    cv2.imshow("Tracked Objects", img)
                    cv2.waitKey(5)



    def shutdown(self):
        print("quitting...")
        self.quit = True
        self.cam.release()
        cv2.destroyAllWindows()
        quit()

    def toggle_overlay(self):
        if self.overlay == "filter_settings":
            self.filter.live_setting()
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
                self.state = "standby"
                print("Stoping Tracking. On standby...")
                del self.finder

            elif self.payload[0] == "new_template" and self.state == "standby":
                print("Received new Template. Changing to tracking mode")
                self.new_template(self.payload[1])
                self.overlay = "filter_settings"

            elif self.payload[0] == "track":
                print("Trying to open template",self.payload[1])
                template = Template(template_path=self.settings["template_filepath"]+self.payload[1])
                self.filter = TemplateTracker(self, template, process=True)
                self.state = "tracking"


            if self.payload[0] == "overlay" and not self.overlay:
                self.overlay = self.payload[1]

            self.payload = None

    #---------------------------------------------------------------------------
    # Image Processing
    #---------------------------------------------------------------------------
    def draw_contour(self, matches, img):
        if not matches:
            return img
        for p, c, d  in matches:
            cv2.circle(img, p, 7, (0,0,255), -1)
            cv2.putText(img, str(p[0])+"|"+str(p[1]), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
            cv2.drawContours(img, c, -1, (0,255,0), 2)

            return img

    def new_template(self, file_name):
        filepath = self.settings["template_filepath"] + file_name
        template = Template(img_path=filepath)
        self.filter = TemplateTracker(self, template)


    def adjust_filter_settings(self):
        print("Engaging filter settings mode")

        window = "Filter Settings"
        cv2.namedWindow(window)
        cv2.createTrackbar("Threshold",window,0,255,self.nothing)

        while True:
            self.process_inbox()
            _, img = self.cam.read()
            quit = self.key_events()
            if quit:
                break

            threshold = cv2.getTrackbarPos("Threshold",window)
            self.settings["threshold"] = threshold
            self.filter.update_settings(self.settings)

            filtered_img = self.filter.apply(img)


            cv2.imshow(window, filtered_img)
        cv2.destroyWindow(window)
        self.overlay = None

        return

    def nothing(self,x):
        pass

    def adjust_finder_settings(self):
        print("Engaging finder settings mode")

        while True:
            self.process_inbox()
            _, img = self.cam.read()
            if quit:
                break


            filtered_img = self.filter.apply(img)
            candidates = self.finder.find_candidates(filtered_img)

            img = self.draw_contour(candidates, img)
            cv2.imshow(window,img)

        cv2.destroyAllWindows()
        self.overlay = None

        return





    def exit_key(self):
        k = cv2.waitKey(5) % 0xFF
        if k%256 == 27:
            self.quit = True
            self.shutdown()


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

class Template:
    def __init__(self, img_path=None, template_path=None):
        if img_path:
            self.img = cv2.imread(img_path,cv2.IMREAD_COLOR)
            self.config_file = img_path[:-4] + ".config"
            self.config = {
            "BinaryLower"      : 100,
            "BinaryUpper"      : 255,
            "Blur"             : 0,
            "HueLower"         : 0,
            "HueUpper"         : 255,
            "SaturationLower"  : 0,
            "SaturationUpper"  : 255,
            "ValueLower"       : 0,
            "ValueUpper"       : 255,
            "MaxDistance"      : 20, # Is divided by 20 befor application
            "AreaFilter"       : 500,
            "PerimeterFilter"  : 500,
            "BinaryMethod"     : 1,
            }

        if template_path:
            self.config = dict()
            self.config = self.read_config(template_path+".config")
            self.img = cv2.imread(template_path+".png",cv2.IMREAD_COLOR)

    def read_config(self, path):
        with open(path,"r") as file:
            for line in file:
                if line[0] == "#" or line[0] == "":
                    continue
                line = line.rstrip().split("=")
                print(line)
                self.config[line[0]] = int(line[1])

        return self.config

    def get_hsv_lower(self):
        return self.config["HueLower"], self.config["SaturationLower"], self.config["ValueLower"]

    def get_hsv_upper(self):
        return self.config["HueUpper"], self.config["SaturationUpper"], self.config["ValueUpper"]

    def save_config(self):
        with open(self.config_file,"w") as file:
            for key in self.config:
                file.write(key+"="+str(self.config[key])+"\n")



class TemplateTracker:
    def __init__(self, app, template, process=False):
        self.app = app
        self.settings = app.settings
        self.template = template
        self.window = "Settings"

        self.match_method = []

        if process:
            self.template.contours = self.filter(self.template.img)


    def filter(self, img):
        color_mask, color_img = self.color(img)
        filtered_img = self.binary(color_img)
        contours = self.get_contour(filtered_img)

        return contours

    def go(self, img):
        contours = self.filter(img)
        matches = self.get_matches(contours, self.template.contours)

        return matches

    def apply(self, img):
        img = self.binary(img)
        return img

    def update_settings(self, settings):
        self.settings = settings

    def binary_band_inv(self, img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _,img = cv2.threshold(img, self.template.config["BinaryUpper"],255, cv2.THRESH_TOZERO_INV)
        _,img = cv2.threshold(img, self.template.config["BinaryLower"],255, cv2.THRESH_BINARY_INV)
        return img

    def binary_band(self,img):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _,img = cv2.threshold(img, self.template.config["BinaryUpper"],255, cv2.THRESH_TOZERO_INV)
        _,img = cv2.threshold(img, self.template.config["BinaryLower"],255, cv2.THRESH_BINARY)
        return img

    def blur(self,img):
        blur_mode = self.template.config["Blur"]
        if blur_mode == 0:
            return img
        if blur_mode == 1:
            return cv2.GaussianBlur(img, (5,5), 0)
        if blur_mode == 2:
            return cv2.medianBlur(img,5)
        if blur_mode == 3:
            return cv2.bilateralFilter(img,9,75,75)

    def color(self, img):
        mask = cv2.inRange(img, self.template.get_hsv_lower(), self.template.get_hsv_upper())
        res = cv2.bitwise_and(img,img,mask=mask)
        return mask, res

    def get_contour(self, img):
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        return contours

    def area_filter(self, matches):
        if not matches:
            return
        if self.template.config["AreaFilter"] == 0:
            return matches

        f_matches = list()
        for p, c, d, a, l in matches:
            if self.template.area + self.template.config["AreaFilter"] > a > self.template.area - self.template.config["AreaFilter"]:
                f_matches.append([p, c, d, a, l])

        return f_matches

    def perimeter_filter(self, matches):
        if not matches:
            return
        if self.template.config["PerimeterFilter"] == 0:
            return matches

        f_matches = list()
        for p, c, d, a, l in matches:
            if self.template.perimeter + self.template.config["PerimeterFilter"] > l > self.template.perimeter - self.template.config["PerimeterFilter"]:
                f_matches.append( [p,c,d,a,l] )

        return f_matches

    def get_matches(self, c_contours, t_contours):

        matches = list()

        for c in c_contours:
            if t_contours:
                distance = cv2.matchShapes(t_contours[0], c, cv2.CONTOURS_MATCH_I1,0)
            else:
                return
            if distance < self.template.config["MaxDistance"]: #Schwellenwert
                matches.append( (self.get_center(c), c, distance, cv2.contourArea(c), cv2.arcLength(c, True)) )

        return matches

    def get_center(self, contour):
        M = cv2.moments(contour)
        try:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
        except ZeroDivisionError:
            cX, cY = 0, 0

        return cX, cY

    def draw_contour(self, candidates, img):
        if not candidates:
            return img
        for p, c, d, a, l  in candidates:
            cv2.circle(img, p, 7, (0,0,255), -1)
            cv2.putText(img, str(a)+"|"+str(l), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
            #cv2.putText(img, str(p[0])+"|"+str(p[1]), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
            cv2.drawContours(img, c, -1, (0,255,0), 2)

        return img

    def apply_config(self):
        img = self.template.img
        color_mask, color_img = self.color(img)
        filtered_img = self.binary(color_img)

        candidates = self.get_contour(filtered_img, t_filtered_img)
        # TODO: get_contour separate, function für den ganzen filterstack

    def track(self):
        apply_config()


    def live_setting(self):

        mock_img = np.zeros( (1,500,3), np.uint8)

        cv2.namedWindow("Template")
        cv2.namedWindow(self.window)
        cv2.createTrackbar("View",self.window,4,4,nothing)
        cv2.createTrackbar("Blur",self.window,self.template.config["Blur"],3,nothing)
        cv2.createTrackbar("Binary Method", self.window, self.template.config["BinaryMethod"],2,nothing)
        cv2.createTrackbar("Binary Lower",self.window,self.template.config["BinaryLower"],255,nothing)
        cv2.createTrackbar("Binary Upper",self.window,self.template.config["BinaryUpper"],255,nothing)
        cv2.createTrackbar("Hue Lower",self.window,self.template.config["HueLower"],255,nothing)
        cv2.createTrackbar("Hue Upper",self.window,self.template.config["HueUpper"],255,nothing)
        cv2.createTrackbar("Saturation Lower",self.window,self.template.config["SaturationLower"],255,nothing)
        cv2.createTrackbar("Saturation Upper",self.window,self.template.config["SaturationUpper"],255,nothing)
        cv2.createTrackbar("Value Lower", self.window,self.template.config["ValueLower"],255,nothing)
        cv2.createTrackbar("Value Upper",self.window,self.template.config["ValueUpper"],255,nothing)
        cv2.createTrackbar("Max Distance", self.window, self.template.config["MaxDistance"],100,nothing)
        cv2.createTrackbar("Area", self.window, self.template.config["AreaFilter"],2000,nothing)
        cv2.createTrackbar("Perimeter", self.window, self.template.config["PerimeterFilter"],2000,nothing)


        while True:
            self.app.process_inbox()
            _, img = self.app.cam.read()
            quit = self.key_events()
            if quit:
                break

            view = cv2.getTrackbarPos("View",self.window)
            self.template.config["Blur"] = cv2.getTrackbarPos("Blur",self.window)
            self.template.config["BinaryMethod"] = cv2.getTrackbarPos("Binary Method",self.window)
            self.template.config["BinaryLower"] = cv2.getTrackbarPos("Binary Lower",self.window)
            self.template.config["BinaryUpper"] = cv2.getTrackbarPos("Binary Upper",self.window)
            self.template.config["HueLower"] = cv2.getTrackbarPos("Hue Lower",self.window)
            self.template.config["HueUpper"] = cv2.getTrackbarPos("Hue Upper",self.window)
            self.template.config["SaturationLower"] = cv2.getTrackbarPos("Saturation Lower",self.window)
            self.template.config["SaturationUpper"] = cv2.getTrackbarPos("Saturation Upper",self.window)
            self.template.config["ValueLower"] = cv2.getTrackbarPos("Value Lower",self.window)
            self.template.config["ValueUpper"] = cv2.getTrackbarPos("Value Upper",self.window)
            self.template.config["MaxDistance"] = cv2.getTrackbarPos("Max Distance",self.window)
            self.template.config["AreaFilter"] = cv2.getTrackbarPos("Area", self.window)
            self.template.config["PerimeterFilter"] = cv2.getTrackbarPos("Perimeter", self.window)

            blur_img = self.blur(img)
            t_blur_img = self.blur(self.template.img)


            color_mask, color_img = self.color(blur_img)
            t_color_mask, t_color_img = self.color(t_blur_img)

            if self.template.config["BinaryMethod"] == 0:
                filtered_img = self.binary_band(color_img)
                t_filtered_img = self.binary_band(t_color_img)
            elif self.template.config["BinaryMethod"] == 1:
                filtered_img = self.binary_band_inv(color_img)
                t_filtered_img = self.binary_band_inv(t_color_img)
            elif self.template.config["BinaryMethod"] == 2:
                filtered_img = cv2.Canny(color_img, self.template.config["BinaryLower"],self.template.config["BinaryUpper"])
                t_filtered_img = cv2.Canny(t_color_img, self.template.config["BinaryLower"],self.template.config["BinaryUpper"])

            contours = self.get_contour(filtered_img)
            t_contours = self.get_contour(t_filtered_img)


            matches = self.get_matches(contours, t_contours)
            if t_contours:
                self.template.area = cv2.contourArea(t_contours[0])
                self.template.perimeter = cv2.arcLength(t_contours[0], True)

            f_matches = self.area_filter(matches)
            f_matches = self.perimeter_filter(f_matches)

            if view == 0:
                cv2.imshow(self.window, mock_img)
                cv2.imshow("Template", t_color_mask)
                cv2.imshow("Camera Stream", color_mask)
            elif view == 1:
                cv2.imshow(self.window, mock_img)
                cv2.imshow("Template", t_color_img)
                cv2.imshow("Camera Stream", color_img)
            elif view == 2:
                cv2.imshow(self.window, mock_img)
                cv2.imshow("Template", t_filtered_img)
                cv2.imshow("Camera Stream", filtered_img)
            elif view == 3:
                img = self.draw_contour(matches, img)
                cv2.imshow(self.window, mock_img)
                cv2.imshow("Camera Stream",img)

                t_img = self.template.img.copy()
                if t_contours:
                    p = self.get_center(t_contours[0])
                    cv2.circle(t_img, p, 7, (0,0,255), -1)
                    cv2.putText(t_img, str(cv2.contourArea(t_contours[0]))+"|"+str(cv2.arcLength(t_contours[0],True)), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
                    #cv2.putText(img, str(p[0])+"|"+str(p[1]), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
                    cv2.drawContours(t_img, t_contours[0], -1, (0,255,0), 2)
                cv2.imshow("Template", t_img)
            elif view == 4:
                img = self.draw_contour(f_matches, img)
                cv2.imshow(self.window, mock_img)
                cv2.imshow("Camera Stream",img)

                t_img = self.template.img.copy()
                if t_contours:
                    p = self.get_center(t_contours[0])
                    cv2.circle(t_img, p, 7, (0,0,255), -1)
                    cv2.putText(t_img, str(cv2.contourArea(t_contours[0]))+"|"+str(cv2.arcLength(t_contours[0],True)), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
                    #cv2.putText(img, str(p[0])+"|"+str(p[1]), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
                    cv2.drawContours(t_img, t_contours[0], -1, (0,255,0), 2)
                    cv2.imshow("Template", t_img)

            cv2.waitKey(5)
        cv2.destroyAllWindows()
        self.overlay = None

        return


    def key_events(self):
        k = cv2.waitKey(5) % 0xFF

        if k == ord("s"):
            self.app.settings = self.settings
            self.app.save_settings()

        if k == ord("s"):
            print("Saving Template")
            self.template.save_config()

        if k == ord("q"):
            return True


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
            if distance < self.settings["max_distance"]/100: #Schwellenwert
                candidates.append(TrackedObject(c, distance))

        return candidates

def nothing(x):
    pass


if __name__ == "__main__":
    App().main_loop()
