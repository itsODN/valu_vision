import cv2
import paho.mqtt.client
from operator import itemgetter
import numpy as np

class App:
    def __init__(self):

        self.setup()

        self.mqtt         = MQTT_Client(self)

        self.cycle     = 0
        self.pub_freq  = 10
        self.tracker   = None
        self.quit      = False
        self.payload   = None
        self.template  = None
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
            self.process_inbox()

            if self.state == "setup":
                self.tracker.update()
                self.tracker.update_trackbars()
                self.tracker.render()

            if self.state == "tracking":
                matches = self.tracker.update()
                self.tracker.show()
                self.publish_result(matches)




    def shutdown(self):
        print("quitting...")
        self.quit = True
        cv2.destroyAllWindows()
        quit()

    #---------------------------------------------------------------------------
    # communication
    #---------------------------------------------------------------------------
    def publish_result(self, matches):
        self.cycle += 1
        if self.cycle >= self.pub_freq:
            self.cycle = 0
            if matches:
                msg = str(matches[0][0][0])+";"+str(matches[0][0][1])
            else:
                msg = "Nothing Found"
            print("Sending:",msg)
            self.mqtt.publish(msg)

    def receive(self, msg):
        self.payload = str(msg)[2:-1].split(";")
        return

    def process_inbox(self):
        self.mqtt.update()
        if self.payload:
            if self.payload[0] == "quit":
                self.shutdown()

            elif self.payload[0] == "new":
                self.new_template(self.payload[1])

            elif self.payload[0] == "load":
                self.load_template(self.payload[1])


            self.payload = None

    def new_template(self, img_path):
        print("Setting up new template with image:",img_path)
        #TODO check if file exists
        tem = Template()
        tem.new(self.settings["template_filepath"]+img_path)
        if self.tracker:
            del self.tracker
        self.tracker = TemplateTracker(self,tem)
        self.tracker.live_init()
        self.state = "setup"

    def load_template(self, tem_name):
        print("Loading template",tem_name)
        tem = Template()
        tem.load(self.settings["template_filepath"]+tem_name)
        if self.tracker:
            del self.tracker
        self.tracker = TemplateTracker(self, tem)
        self.state = "tracking"

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


class Template:
    def __init__(self):
        pass

    def new(self, name):
        self.name = name
        self.config_file = name[:-4]+".config"
        self.img = cv2.imread(name,cv2.IMREAD_COLOR)
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

    def load(self, name):
        self.name = name
        self.config = dict()
        self.config = self.read_config(self.name+".config")
        self.img = cv2.imread(self.name+".png",cv2.IMREAD_COLOR)

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
    def __init__(self, app, template):
        self.app = app
        self.settings = app.settings
        self.cam = cv2.VideoCapture(self.settings["camera_number"])
        self.template = template
        self.window = "Settings"
        self.view = 4
        self.mock_img = np.zeros( (1,500,3), np.uint8)

        self.match_method = []

    def __del__(self):
        self.cam.release()
        cv2.destroyAllWindows()


    def update(self):
        _, self.img = self.cam.read()

        self.blur_img = self.blur(self.img)
        self.t_blur_img = self.blur(self.template.img)


        self.color_mask, self.color_img = self.color(self.blur_img)
        self.t_color_mask, self.t_color_img = self.color(self.t_blur_img)

        if self.template.config["BinaryMethod"] == 0:
            self.filtered_img = self.binary_band(self.color_img)
            self.t_filtered_img = self.binary_band(self.t_color_img)
        elif self.template.config["BinaryMethod"] == 1:
            self.filtered_img = self.binary_band_inv(self.color_img)
            self.t_filtered_img = self.binary_band_inv(self.t_color_img)
        elif self.template.config["BinaryMethod"] == 2:
            self.filtered_img = cv2.Canny(self.color_img, self.template.config["BinaryLower"],self.template.config["BinaryUpper"])
            self.t_filtered_img = cv2.Canny(self.t_color_img, self.template.config["BinaryLower"],self.template.config["BinaryUpper"])

        self.contours = self.get_contour(self.filtered_img)
        self.t_contours = self.get_contour(self.t_filtered_img)


        self.matches = self.get_matches(self.contours, self.t_contours)
        if self.t_contours:
            self.template.area = cv2.contourArea(self.t_contours[0])
            self.template.perimeter = cv2.arcLength(self.t_contours[0], True)

        self.f_matches = self.area_filter(self.matches)
        self.f_matches = self.perimeter_filter(self.f_matches)

        return self.f_matches

    #---------------------------------------------------------------------------
    # Filters
    #---------------------------------------------------------------------------
    def filter(self, img):
        color_mask, color_img = self.color(img)
        filtered_img = self.binary(color_img)
        contours = self.get_contour(filtered_img)

        return contours

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

    #---------------------------------------------------------------------------
    # Matching Tools
    #---------------------------------------------------------------------------
    def get_contour(self, img):
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        return contours

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

    def apply_config(self):
        img = self.template.img
        color_mask, color_img = self.color(img)
        filtered_img = self.binary(color_img)

        candidates = self.get_contour(filtered_img, t_filtered_img)
        # TODO: get_contour separate, function für den ganzen filterstack



    #---------------------------------------------------------------------------
    # GUI Tools
    #---------------------------------------------------------------------------
    def live_init(self):
        self.setup_trackbars()

    def draw_contour(self, candidates, img):
        if not candidates:
            return img
        for p, c, d, a, l  in candidates:
            cv2.circle(img, p, 7, (0,0,255), -1)
            cv2.putText(img, str(a)+"|"+str(l), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
            #cv2.putText(img, str(p[0])+"|"+str(p[1]), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
            cv2.drawContours(img, c, -1, (0,255,0), 2)

        return img

    def setup_trackbars(self):
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

    def update_trackbars(self):
        self.view = cv2.getTrackbarPos("View",self.window)
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

    def show(self):
        img = self.img.copy()
        img = self.draw_contour(self.f_matches, img)
        cv2.imshow("Camera Stream",img)
        cv2.waitKey(5)


    def render(self):
        img = self.img.copy()
        if self.view == 0:
            cv2.imshow(self.window, self.mock_img)
            cv2.imshow("Template", self.t_color_mask)
            cv2.imshow("Camera Stream", self.color_mask)
        elif self.view == 1:
            cv2.imshow(self.window, self.mock_img)
            cv2.imshow("Template", self.t_color_img)
            cv2.imshow("Camera Stream", self.color_img)
        elif self.view == 2:
            cv2.imshow(self.window, self.mock_img)
            cv2.imshow("Template", self.t_filtered_img)
            cv2.imshow("Camera Stream", self.filtered_img)
        elif self.view == 3:
            img = self.draw_contour(self.matches, img)
            cv2.imshow(self.window, self.mock_img)
            cv2.imshow("Camera Stream",img)

            t_img = self.template.img.copy()
            if self.t_contours:
                p = self.get_center(self.t_contours[0])
                cv2.circle(t_img, p, 7, (0,0,255), -1)
                cv2.putText(t_img, str(cv2.contourArea(self.t_contours[0]))+"|"+str(cv2.arcLength(self.t_contours[0],True)), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
                #cv2.putText(img, str(p[0])+"|"+str(p[1]), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
                cv2.drawContours(t_img, self.t_contours[0], -1, (0,255,0), 2)
            cv2.imshow("Template", t_img)
        elif self.view == 4:
            img = self.draw_contour(self.f_matches, img)
            cv2.imshow(self.window, self.mock_img)
            cv2.imshow("Camera Stream",img)

            t_img = self.template.img.copy()
            if self.t_contours:
                p = self.get_center(self.t_contours[0])
                cv2.circle(t_img, p, 7, (0,0,255), -1)
                cv2.putText(t_img, str(cv2.contourArea(self.t_contours[0]))+"|"+str(cv2.arcLength(self.t_contours[0],True)), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
                #cv2.putText(img, str(p[0])+"|"+str(p[1]), (p[0] -20, p[1] -20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
                cv2.drawContours(t_img, self.t_contours[0], -1, (0,255,0), 2)
                cv2.imshow("Template", t_img)
        self.key_events()


    def key_events(self):
        k = cv2.waitKey(5) % 0xFF

        if k == ord("q"):
            self.end_setup()

        if k == 27:
            self.abort_setup()

        if k == ord("s"):
            print("Saving Parameters to config file")
            self.template.save_config()


    def end_setup(self):
        print("leaving setup")
        cv2.destroyAllWindows()
        self.app.state = "tracking"

    def abort_setup(self):
        print("aborting setup")
        cv2.destroyAllWindows()
        self.app.state = "standby"




def nothing(x):
    pass


if __name__ == "__main__":
    App().main_loop()
