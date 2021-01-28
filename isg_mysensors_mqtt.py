#
# This is the MQTT communication module for the ISG daemon
# Deals with MQTT subscribe / publish / messages / etc

import paho.mqtt.client as mqtt
from isg_mysensors_constants import *


class ISGmqtt:

    def __init__(self, in_mqtt_section, in_mysensors_section, in_when_message,
                 in_sensor_types, in_sensor_names, in_logger):
        in_logger.debug(f"""ISGmqtt __init__ {in_mqtt_section} {in_mysensors_section} {in_when_message} 
                         {in_sensor_types} {in_sensor_names} {in_logger}""")

        self.logger = in_logger

        self.mqtt_client = mqtt.Client(in_mqtt_section[mqttClient], True)
        self.mqtt_client.on_connect = self.when_connect
        self.mqtt_client.on_message = self.when_message

        self.call_when_message = in_when_message

        self.subscribe = in_mqtt_section[mqttSubscribe] + "/#"
        self.publish_topic = in_mqtt_section[mqttPublish] + "/"

        self.node_id = in_mysensors_section[mySensorsNodeID]
        self.node_name = in_mysensors_section[mySensorsNodeName]

        self.connect(in_mqtt_section[mqttHost], int(in_mqtt_section[mqttPort]), int(in_mqtt_section[mqttKeepalive]))

        self.presentation(in_sensor_types, in_sensor_names)

    def connect(self, in_host, in_port, in_keepalive):
        self.logger.debug(f"ISGmqtt connect {in_host} {in_port} {in_keepalive}")
        self.mqtt_client.connect(in_host, in_port, in_keepalive)

    # The callback for when the client receives a CONNACK response from the server.
    def when_connect(self, client, userdata, flags, rc):
        self.logger.debug(f"ISGmqtt when_connect {client} {userdata} {flags} {rc}")
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        #        print("Connected with result code "+str(rc))
        #        print(self.config[mqttSection][mqttSubscribe]+"/#")
        self.mqtt_client.subscribe(self.subscribe)
        self.run_loop(5)

    # The callback for when a PUBLISH message is received from the server.
    def when_message(self, client, userdata, msg):
        self.logger.debug(f"ISGmqtt when_message {client} {userdata} {msg}")
        print(msg.topic + " " + str(msg.payload))
        msg_split = msg.topic.split("/")
        msg_node_id = msg_split[1]
        msg_sensor_id = msg_split[2]
        msg_command = msg_split[3]
        msg_type = msg_split[5]

        self.call_when_message(msg_node_id, msg_sensor_id, msg_command, msg_type, msg.payload)

    def run_loop(self, in_seconds):
        self.logger.debug(f"ISGmqtt run_loop {in_seconds}")
        self.mqtt_client.loop(in_seconds)

    def presentation(self, in_sensor_types, in_sensor_names):
        self.logger.debug(f"ISGmqtt presentation {in_sensor_types} {in_sensor_names}")
        # Announce the Gateway as a repeater node
        #            self.mqttClient.publish("ISG/0/255/0/0/18", "1.2.3")
        self.mqtt_client.publish(self.publish_topic + self.node_id + "/255/0/0/18", softwareVersion)

        # Announce the "sketch" and "version"
        #            self.mqttClient.publish("ISG/0/255/3/0/11", "ISG Node")
        self.mqtt_client.publish(self.publish_topic + self.node_id + "/255/3/0/11", self.node_name)
        #            self.mqttClient.publish("ISG/0/255/3/0/12", "1.2.3")
        self.mqtt_client.publish(self.publish_topic + self.node_id + "/255/3/0/12", softwareVersion)

        # Announce all of the sensors
        #            self.mqttClient.publish("ISG/100/0/0/0/6", "Outside temp")
        for sensor_id in in_sensor_names.keys():
            self.mqtt_client.publish(self.publish_topic + self.node_id + "/" +
                                     str(sensor_id) + "/0/0/" + in_sensor_types[sensor_id],
                                     in_sensor_names[sensor_id])

        self.run_loop(5)

    def discover_response(self):
        self.logger.debug(f"ISGmqtt discover_response")
    #            self.mqttClient.publish("ISG/0/255/3/0/21", 0)
        self.mqtt_client.publish(self.publish_topic + self.node_id + "/255/" +
                                 COMMAND_INTERNAL + "/0/" + I_DISCOVER_RESPONSE, self.node_id)

    def publish_value(self, in_sensor, in_variable_type, in_sensor_value):
        self.logger.debug(f"ISGmqtt discover_response {in_sensor} {in_variable_type} {in_sensor_value}")
        self.mqtt_client.publish(self.publish_topic + self.node_id + "/" + str(in_sensor) + "/1/0/" + in_variable_type,
                                 in_sensor_value)

    def run_stop(self):
        self.logger.debug(f"ISGmqtt run_stop")
        self.mqtt_client.stop_loop()