#
# This handles the parsing and management of the config file
#

import configparser
from isg_mysensors_constants import *


class ISGConfig:

    def __init__(self, in_config_fileName, in_logger):
        in_logger.debug(f"isg_config __init__ {in_config_fileName}")

        self.config_file_name = in_config_fileName
        self.logger = in_logger

        self.config = configparser.ConfigParser(allow_no_value=True)
        self.config.read(in_config_fileName)

        self.node_id = self.config[mySensorsSection][mySensorsNodeID]
        self.modbus_host = self.config[serverSection][serverHost]
        self.modbus_port = int(self.config[serverSection][serverPort])

        self.sensorNames = {}
        self.registerTypes = {}
        self.registerDataTypes = {}
        self.sensorRealTypes = {}
        self.registerBitValues = {}
        self.registerBit = {}
        self.sensorRefresh = {}
        self.registerSensorIds = {}
        self.sensorRegisters = {}
        self.sensorTypes = {}
        self.variableTypes = {}
        self.sensorIntervals = {}
        self.sensorPublishTimes = {}

        self.section_list = {}

        self.mqtt = False

        self.loops = -1

    def refresh_config(self):
        self.logger.debug(f"config refreshConfig")

        self.config = configparser.ConfigParser(allow_no_value=True)
        self.config.read(self.config_file_name)

        self.node_id = self.config[mySensorsSection][mySensorsNodeID]

        section_list = self.config.sections()
        if serverSection in section_list:
            section_list.remove(serverSection)
        if mqttSection in section_list:
            section_list.remove(mqttSection)
        if mySensorsSection in section_list:
            section_list.remove(mySensorsSection)
        if debugSection in section_list:
            section_list.remove(debugSection)

        for section in section_list:
            if int(self.config[section][sensorId]) >= 0:
                sensor = int(self.config[section][sensorId])
                register = self.config[section][registerAddress]
                self.sensorRegisters[sensor] = register
                self.sensorNames[sensor] = self.config[section][sensorName]
                self.registerTypes[sensor] = self.config[section][registerType]
                self.registerDataTypes[sensor] = int(self.config[section][registerDataType])
                self.sensorRefresh[sensor] = int(self.config[section][sensorRefresh])
                self.sensorRegisters[sensor] = register
                self.sensorTypes[sensor] = self.config[section][sensorType]
                self.variableTypes[sensor] = self.config[section][variableType]
                if sensorPublishTime in self.config[section]:
                    self.sensorPublishTimes[sensor] = self.config[section][sensorPublishTime]
                elif sensorInterval in self.config[section]:
                    self.sensorIntervals[sensor] = self.config[section][sensorInterval]

                self.sensorRealTypes[sensor] = 'normal'
                if registerLong in self.config[section]:
                    self.sensorRealTypes[sensor] = 'long'
                elif registerBit in self.config[section]:
                    self.sensorRealTypes[sensor] = 'bit'
                    self.registerBit[sensor] = int(self.config[section][registerBit])
                elif register_interval in self.config[section]:
                    self.sensorRealTypes[sensor] = 'interval'
                elif register_idle in self.config[section]:
                    self.sensorRealTypes[sensor] = 'idle'

        if debugSection in self.config.sections():
            if debugLoops in self.config[debugSection]:
                self.loops = int(self.config[debugSection][debugLoops])

        if mqttSection in self.config.sections():
            self.mqtt = True

        # Clever way of getting a sorted integer list (from strings...)
        # reg_num_list = [int(x) for x in [*self.sensorRegisters.values()]]  # Convert to integer list
        reg_num_list = list(set(self.sensorRegisters.values()))
        # reg_num_list.sort(key=int)  # Sort (in place)
        reg_num_list.sort()  # Sort (in place)

        return reg_num_list

    def mqtt_section(self):
        self.logger.debug(f"config mqtt_section")

        return self.config[mqttSection]

    def mysensors_section(self):
        self.logger.debug(f"config mqtt_section")

        return self.config[mySensorsSection]
