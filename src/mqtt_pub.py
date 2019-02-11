import paho.mqtt.client
from time import sleep


class MQTT_Client:
    def __init__(self):
        self.client = paho.mqtt.client.Client()

        self.input_topic  = "iot/data/ssfcic/camera_tracking/position"
        self.output_topic = "iot/data/ssfcic/camera_tracking/commands"

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
        print("Received Message:",msg.payload)

    def on_subscribe(self, client, userdata, mid, granted_qos):
        print("Subscribed to:", client, userdata, mid, granted_qos)

    def update(self):
        self.client.loop(0.1)

    def publish(self, msg):
        print("publishing:",msg,"to",self.output_topic)
        self.client.publish(self.output_topic, str(msg))


def main():
    quit = False
    m = MQTT_Client()
    for i in range(20):
        m.update()
        if i == 1:
            m.publish("new_template;test.png")
        if i == 7:
            m.publish("stop_tracking")
        if i == 8:
            m.publish("new_template;test2.png")

        if i == 15:
            m.publish("quit")
        sleep(1)




if __name__ ==  "__main__":
    main()
