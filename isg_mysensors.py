import time
import logging
from isg_mysensors_constants import *
from isg_mysensors_config import ISGConfig
from isg_mysensors_modbus import modbus
from isg_mysensors_mqtt import ISGmqtt
from isg_mysensors_http import http

# TODO: Drop config stuff - build as constants in a constants module


# ----------------------------------------------------------------
#
# This class refreshes its values on an "as-needed" basis.
# Request a value or print it and it will check if the refresh
# interval (defined in the config) has been exceeded.
#
# ----------------------------------------------------------------
class ISGReader:

    def __init__(self, in_config_filename):
        logger.debug(f"ISGReader __init__ {in_config_filename}")

        self.config = ISGConfig(in_config_filename, logger)
        reg_num_list = self.config.refresh_config()

        self.modbus_client = modbus(self.config.modbus_host, int(self.config.modbus_port), logger)
        self.modbus_client.build_blocks(reg_num_list)

        self.http_reader = http(self.config.modbus_host, logger)

        if self.config.mqtt:
            self.mqtt_client = ISGmqtt(self.config.mqtt_section(), self.config.mysensors_section(), self.when_message,
                                       self.config.sensorTypes, self.config.sensorNames, logger)

        # Read the HC and DHW programmes from the ISG and send them to the controller in a special message
        self.mqtt_client.send_control_message("HC", COMMAND_SET, self.http_reader.refresh_raw_values(1))
        self.mqtt_client.send_control_message("DHW", COMMAND_SET, self.http_reader.refresh_raw_values(2))

    def close_client(self):
        logger.debug(f"ISGReader close_client")
        self.modbus_client.run_close()
        self.mqtt_client.run_stop()

    def sensor_value(self, in_sensor):
        logger.debug(f"ISGReader sensor_value {in_sensor}")

        if self.config.sensorRegisters[in_sensor][0:3] == "val":
            reg_value = self.http_reader.register_value(self.config.sensorRegisters[in_sensor],
                                                        self.config.sensorRefresh[in_sensor],
                                                        self.config.registerDataTypes[in_sensor],
                                                        self.config.sensorRealTypes[in_sensor])
        else:
            reg_value = self.modbus_client.register_value(int(self.config.sensorRegisters[in_sensor]),
                                                          self.config.sensorRefresh[in_sensor],
                                                          self.config.registerDataTypes[in_sensor],
                                                          self.config.sensorRealTypes[in_sensor])
        if self.config.sensorRealTypes[in_sensor] == 'bit':
            return int(reg_value / pow(2, self.config.registerBit[in_sensor])) % 2
        else:
            return reg_value

    # The callback for when a PUBLISH message is received from the server.
    def when_message(self, msg_node_id, msg_sensor_id, msg_command, msg_type, payload):
        logger.debug(f"ISGReader when_message {msg_node_id} {msg_sensor_id} {msg_command} {msg_type} {payload}")

        # Process discover from Controller
        if ((msg_node_id == "255") and
           (msg_command == COMMAND_INTERNAL) and
           (msg_type == I_DISCOVER_REQUEST)):
            self.mqtt_client.discover_response()

        # Process presentation request from Controller
        elif ((msg_node_id == self.config.node_id) and
              (msg_command == COMMAND_INTERNAL) and
              (msg_type == I_PRESENTATION)):
            self.mqtt_client.presentation(self.config.sensorTypes, self.config.sensorNames)

        # Process set sensor value
        elif ((msg_node_id == self.config.node_id) and
              (msg_command == COMMAND_SET)):
            self.set_sensor_value(msg_sensor_id, payload)

        # Process request sensor value
        elif ((msg_node_id == self.config.node_id) and
              (msg_command == COMMAND_REQ)):
            self.publishValue(int(msg_sensor_id))

    def publishValue(self, in_sensor):
        logger.debug(f"ISGReader publishValue {in_sensor}")
        if self.config.mqtt:
            self.mqtt_client.publish_value(str(in_sensor),
                                           self.config.variableTypes[in_sensor],
                                           self.sensor_value(in_sensor))

    def set_sensor_value(self, in_sensor_id, in_value):
        logger.debug(f"ISGReader set_sensor_value {in_sensor_id} {in_value}")

        if in_sensor_id[0:3] == "val":
            self.http_reader.write_register(in_sensor_id, in_value)

        else:
            sensor_id = int(in_sensor_id)
            register = int(self.config.sensorRegisters[sensor_id])
            if self.config.registerTypes[sensor_id] != "read/write":
                logger.warning(f"Tried to write to non-writeable register {register} - sensor ID {sensor_id}")
                return 1

            self.modbus_client.write_register(sensor_id, register, self.config.registerDataTypes[sensor_id], in_value)

            self.publishValue(sensor_id)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
f_handler = logging.FileHandler("/var/log/isg_mysensors/isgmysensors.log")
f_handler.setLevel(logging.INFO)
f_format = logging.Formatter("%(asctime)s:%(levelname)s: %(message)s")
f_handler.setFormatter(f_format)
logger.addHandler(f_handler)

logger.info("ISG Reader started")


ISG = ISGReader('isgmodbus.cfg')

# print(ISG)
# print(ISG.registerNameValue(507))
# print(ISG.registerNameValue(536))
# print(ISG.registerNameValue(2501))
# print(ISG.registerNameValue(3515))
# print(ISG.sensorRefresh)

time_to_publish = {}

for sensor in ISG.config.sensorNames.keys():

    previous_time = time.time() - 1

    # This ensures every sensor is published straight away
    time_to_publish[sensor] = previous_time

loops = ISG.config.loops


pause_time = 0

while loops != 0:
    logger.debug(f"In loop waiting for {pause_time} seconds")

    ISG.mqtt_client.run_loop(pause_time)

    current_time = time.time()

    # This loop should ensure that pick up anything that falls into publish time
    # while we are busy publishing other sensors
    while min(time_to_publish.values()) <= current_time:
        logger.debug(f"In loop current_time =  {current_time}")

        # Publish those that have reached their refresh interval
        for sensor in ISG.config.sensorIntervals.keys():
            if time_to_publish[sensor] <= current_time:
                ISG.publishValue(sensor)
                time_to_publish[sensor] = int(ISG.config.sensorIntervals[sensor]) + current_time
        current_time = time.time()

    logger.debug(f"loop time_to_publish {time_to_publish}")
    # This is failsafe in case we go negative - which causes loop to block
    pause_time = max(min(time_to_publish.values()) - time.time(), 0)

    if loops > 0:
        loops -= 1

ISG.close_client()
