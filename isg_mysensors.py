from easymodbus.modbusClient import ModbusClient
import time, string, logging
from datetime import datetime, timedelta
import configparser
import sys
import paho.mqtt.client as mqtt

# TODO: Break in to classes - separate out the mqtt stuff
# TODO: Drop config stuff - build as constants in a constants module

# Version of this software sent to the Controller
softwareVersion = "1.0.0"

# These are all of the sections / options in the config file for ease of change / visibility
debugSection = 'Debug'
debugLoops = 'Loops'

serverSection = 'Server'
serverHost = 'Host'
serverPort = 'Port'

mqttSection = 'MQTT'
mqttHost = 'Host'
mqttPort = 'Port'
mqttKeepalive = 'Keepalive'
mqttClient = 'Client name'
mqttSubscribe = 'Subscribe topic'
mqttPublish = 'Publish topic'

mySensorsSection = 'MySensors'
mySensorsGateway = 'Gateway name'
mySensorsNodeName = 'Node name'
mySensorsNodeID = 'Node id'

sensorName = 'Name'
registerAddress = 'Address'
registerType = 'Register type'
registerDataType = 'Data type'
registerBit = 'Bit'
registerLong = 'Long'
sensorRefresh = 'Refresh'
sensorId = 'Sensor id'
sensorType = 'Sensor type'
variableType = 'Variable type'
sensorInterval = 'Publish interval'
sensorPublishTime = 'Publish time'

registerTypes = {
        'read':1,
        'read/write':2
        }

readMultiplier = {
        2 : 0.1,
        6 : 1,
        7 : 0.01,
        8 : 1
        }

# Command types from mySensors
COMMAND_PRESENTATION = '0'
COMMAND_SET = '1'
COMMAND_REQ = '2'
COMMAND_INTERNAL = '3'
COMMAND_STREAM = '4'

# Internal message types from mySensors
I_PRESENTATION = '19'
I_DISCOVER_REQUEST = '20'
I_DISCOVER_RESPONSE = '21'

#----------------------------------------------------------------
#
# This class refreshes its values on an "as-needed" basis.
# Request a value or print it and it will check if the refresh
# interval (defined in the config) has been exceeded.
#
#----------------------------------------------------------------
class ISGReader:

    def __init__(self, inConfigFileName):
        logger.debug(f"ISGReader __init__ {inConfigFileName}")


        self.configFileName = inConfigFileName
        self.config = configparser.ConfigParser(allow_no_value=True)
        self.config.read(self.configFileName)

        try:
            self.modbusclient = ModbusClient(self.config[serverSection][serverHost], int(self.config[serverSection][serverPort]))
            self.modbusclient.connect()
        except:
            print(sys.exc_info()[0])
            raise
        
        self.registerValues = {}
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
        self.refreshDateTime = {}
        self.blockStart = {}
        self.blockLength = {}
        self.blockRaw = {}

        self.mqtt = False

        # Only need to read the config at this stage - values will be refreshed when requested
        self.refreshConfig()
        
        self.loops = -1
        if debugSection in self.config.sections():
            if debugLoops in self.config[debugSection]:
                self.loops = int(self.config[debugSection][debugLoops])

        if mqttSection in self.config.sections():
            self.mqtt = True
            self.mqttClient = mqtt.Client(self.config[mqttSection][mqttClient], True)
            self.mqttClient.on_connect = self.when_connect
            self.mqttClient.on_message = self.when_message

            self.mqttClient.connect(
                    self.config[mqttSection][mqttHost],
                    int(self.config[mqttSection][mqttPort]),
                    int(self.config[mqttSection][mqttKeepalive]))

            self.presentation()
            self.mqttClient.loop(5)


    def presentation(self):
        logger.debug(f"ISGReader presentation")
        # Announce the Gateway as a repeater node
#            self.mqttClient.publish("ISG/0/255/0/0/18", "1.2.3")
        self.mqttClient.publish(self.config[mqttSection][mqttPublish] + "/" 
                + self.config[mySensorsSection][mySensorsNodeID] + "/255/0/0/18",
                softwareVersion)

        # Announce the "sketch" and "version"
#            self.mqttClient.publish("ISG/0/255/3/0/11", "ISG Node")
        self.mqttClient.publish(self.config[mqttSection][mqttPublish] + "/" 
                + self.config[mySensorsSection][mySensorsNodeID] + "/255/3/0/11",
                self.config[mySensorsSection][mySensorsNodeName])
#            self.mqttClient.publish("ISG/0/255/3/0/12", "1.2.3")
        self.mqttClient.publish(self.config[mqttSection][mqttPublish] + "/" 
                + self.config[mySensorsSection][mySensorsNodeID] + "/255/3/0/12",
                softwareVersion)

        # Announce all of the sensors
#            self.mqttClient.publish("ISG/100/0/0/0/6", "Outside temp")
        for sensorId in self.sensorList():
            self.mqttClient.publish(self.config[mqttSection][mqttPublish] + "/" 
                    + self.config[mySensorsSection][mySensorsNodeID] + "/"
                    + str(sensorId) + "/0/0/"
                    + self.sensorTypes[sensorId],
                    self.sensorNames[sensorId])

    def __str__(self):
        logger.debug(f"ISGReader __str__")

        out = ''
        for register in self.registerList():
            self.refreshNetValue(register)
            out = out + ("%s> %s : %g\n" % (register, self.registerNameValue(register)['name'], self.registerNameValue(register)['value']))
            if self.registerRealTypes[register] == 'bitcoded':
                for bit in self.registerBitNames[register].keys():
                    out = out + ("%s%s> %s : %g\n" %
                            (register,
                                bit,
                                self.registerBitNames[register][bit],
                                self.registerBitValues[register][bit]))
        return out[:-1]

    def closeClient(self):
        logger.debug(f"ISGReader closeClient")
        self.modbusclient.close()
        self.mqttClient.loop_stop()

    def refreshConfig(self):
        logger.debug(f"ISGReader refreshConfig")

        self.config = configparser.ConfigParser(allow_no_value=True)
        self.config.read(self.configFileName)

        sectionList = self.config.sections()
        if serverSection in sectionList:
            sectionList.remove(serverSection)
        if mqttSection in sectionList:
            sectionList.remove(mqttSection)
        if mySensorsSection in sectionList:
            sectionList.remove(mySensorsSection)
        if debugSection in sectionList:
            sectionList.remove(debugSection)

        for section in sectionList:
            if int(self.config[section][sensorId]) >= 0:
                sensor = int(self.config[section][sensorId])
                register = int(self.config[section][registerAddress])
                self.sensorRegisters[sensor] = register
                self.sensorNames[sensor] = self.config[section][sensorName]
                self.registerTypes[register] = self.config[section][registerType]
                self.registerDataTypes[register] = int(self.config[section][registerDataType])
                self.sensorRefresh[sensor] = int(self.config[section][sensorRefresh])
                self.sensorRegisters[sensor] = register
                self.sensorTypes[sensor] = self.config[section][sensorType]
                self.variableTypes[sensor] = self.config[section][variableType]
                if sensorPublishTime in self.config[section]:
                    self.sensorPublishTimes[sensor] = self.config[section][sensorPublishTime]
                elif sensorInterval in self.config[section]:
                    self.sensorIntervals[sensor] = self.config[section][sensorInterval]
            if registerLong in self.config[section]:
                self.sensorRealTypes[sensor] = 'long'
            elif registerBit in self.config[section]:
                self.sensorRealTypes[sensor] = 'bit'
                self.registerBit[sensor] = int(self.config[section][registerBit])
            else:
                self.sensorRealTypes[sensor] = 'normal'


        # Read in from the device in blocks of max 100 in sections 501-600, 2501-2600, etc

        # Clever way of getting a sorted integer list (from strings...)
        regNumList = [int(x) for x in [*self.registerTypes.keys()]]      # Convert to integer list
        regNumList.sort(key = int)                                 # Sort (in place)

        # Build up the block details by reading through the list of registers and breaking when we find a new 100 max grouping
        curBlock = int((regNumList[0] - 1) / 100)
        self.blockStart[curBlock] = regNumList[0]
        self.blockLength[curBlock] = 2
        self.refreshDateTime[curBlock] = datetime.min              # Set as old as possible so always refreshed on first read

        for readNum in regNumList:
            if int((readNum - 1) / 100) == curBlock:
                self.blockLength[curBlock] = readNum - self.blockStart[curBlock] + 2
            else:
                curBlock = int((readNum - 1) / 100)
                self.blockStart[curBlock] = readNum
                self.blockLength[curBlock] = 2
                self.refreshDateTime[curBlock] = datetime.min

    # Refresh just the block containing the register we are reading
    # Note that the block is the first register value / 100 - eg. 5 = register 500 onwards
    def refreshRawValues(self, inBlock):
        logger.debug(f"ISGReader refreshRawValues {inBlock}")
        # 1500s are read / write holding registers
        if inBlock == 15:
            self.blockRaw[inBlock] = self.modbusclient.read_holdingregisters(self.blockStart[inBlock]-1, self.blockLength[inBlock])
        else:
            self.blockRaw[inBlock] = self.modbusclient.read_inputregisters(self.blockStart[inBlock]-1, self.blockLength[inBlock])
        self.refreshDateTime[self.block] = datetime.now()

    # Only refresh the raw data if the register raw data is stale
    def refreshIfNeeded(self, inRegister, inRefresh):
        logger.debug(f"ISGReader refreshIfNeeded {inRegister} {inRefresh}")

        self.block = int((inRegister - 1) / 100)
        if (datetime.now() > (self.refreshDateTime[self.block] + timedelta(seconds = int(inRefresh)))):
            self.refreshRawValues(self.block)

    def refreshNetValue(self, inRegister, inRefresh, inType):
        logger.debug(f"ISGReader refreshNetValue {inRegister} {inRefresh} {inType}")

        self.refreshIfNeeded(inRegister, inRefresh)
        rawValue = self.blockRaw[int((inRegister-1)/100)][inRegister - self.blockStart[int((inRegister-1)/100)]]
        netValue = int(rawValue) * readMultiplier[self.registerDataTypes[inRegister]]
        #logger.debug(f"register {inRegister} rawvalue {rawValue} netvalue {netValue} readmultiplier {readMultiplier[self.registerDataTypes[inRegister]]} datatype {self.registerDataTypes[inRegister]}")

        if inType == 'long':
            netValue = netValue + self.blockRaw[int((inRegister-1)/100)][inRegister - self.blockStart[int((inRegister-1)/100)]+1] * 1000

        if readMultiplier[self.registerDataTypes[inRegister]] == 1:
            self.registerValues[inRegister] =  int(netValue)
        else:
            self.registerValues[inRegister] =  round(netValue,2)

            return

    def sensorValue(self, inSensor):
        logger.debug(f"ISGReader sensorValue {inSensor}")
#        print("sensorValue " + str(inSensor))
#        print(self.sensorRefresh[inSensor])
#        print(self.sensorRealTypes)
        regValue = self.registerValue(self.sensorRegisters[inSensor], self.sensorRefresh[inSensor], self.sensorRealTypes[inSensor])
        if self.sensorRealTypes[inSensor] == 'bit':
            return (int(regValue / pow(2, self.registerBit[inSensor])) % 2)
        else:
            return regValue

    def registerValue(self, inRegister, inRefresh, inType):
        logger.debug(f"ISGReader registerValue {inRegister} {inRefresh} {inType}")
#        print("registerValue " + str(inRegister) + " " + str(inRefresh))
        self.refreshNetValue(inRegister, inRefresh, inType)
        return self.registerValues[inRegister]

    def registerName(self, inRegister):
        logger.debug(f"ISGReader registerName {inRegister}")
        return self.registerNames[inRegister]

    def registerNameValue(self, inRegister):
        logger.debug(f"ISGReader registerNameValue {inRegister}")
        return {'name': self.registerName(inRegister), 'value': self.registerValue(inRegister)}

    def sensorList(self):
        logger.debug(f"ISGReader sensorList")
        return self.sensorNames.keys()

    # The callback for when the client receives a CONNACK response from the server.
    def when_connect(self, client, userdata, flags, rc):
        logger.debug(f"ISGReader when_connect {client} {userdata} {flags} {rc}")
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
#        print("Connected with result code "+str(rc))
#        print(self.config[mqttSection][mqttSubscribe]+"/#")
        self.mqttClient.subscribe(self.config[mqttSection][mqttSubscribe]+"/#")
        self.mqttClient.loop(5)

    # The callback for when a PUBLISH message is received from the server.
    def when_message(self, client, userdata, msg):
        logger.debug(f"ISGReader when_message {client} {userdata} {msg}")
        print(msg.topic+" "+str(msg.payload))
        msgSplit = msg.topic.split("/")
        msgNodeId = msgSplit[1]
        msgSensorId = msgSplit[2]
        msgCommand = msgSplit[3]
        msgType = msgSplit[5]

        if ((msgNodeId == "255") and
           (msgCommand == COMMAND_INTERNAL) and
           (msgType == I_DISCOVER_REQUEST)):
            self.discoverResponse()

        elif ((msgNodeId == self.config[mySensorsSection][mySensorsNodeID]) and
             (msgCommand == COMMAND_INTERNAL) and
             (msgType == I_PRESENTATION)):
            self.presentation()

        elif ((msgNodeId == self.config[mySensorsSection][mySensorsNodeID]) and
               (msgCommand == COMMAND_SET)):
            self.set_sensor_value(msgSensorId, msg.payload)


    def discoverResponse(self):
        logger.debug(f"ISGReader discoverResponse")
    #            self.mqttClient.publish("ISG/0/255/3/0/21", 0)
        self.mqttClient.publish(self.config[mqttSection][mqttPublish] + "/"
                + self.config[mySensorsSection][mySensorsNodeID] + "/255/"
                + COMMAND_INTERNAL + "/0/"
                + I_DISCOVER_RESPONSE,
                self.config[mySensorsSection][mySensorsNodeID])


    def publishValue(self, inSensor):
        logger.debug(f"ISGReader publishValue {inSensor}")
#        print("publishValue " + str(inSensor))
        if mqttSection in self.config.sections():
            self.mqttClient.publish(self.config[mqttSection][mqttPublish] + "/" 
                    + self.config[mySensorsSection][mySensorsNodeID] + "/"
                    + str(inSensor) + "/1/0/"
                    + self.variableTypes[inSensor],
                    self.sensorValue(inSensor),
                    0)

    def set_sensor_value(self, in_sensor_id, in_value):
        logger.debug(f"ISGReader set_sensor_value {in_sensor_id} {in_value}")
        register = self.sensorRegisters[int(in_sensor_id)]
        if self.registerTypes[register] != "read/write":
            logger.warning(f"Tried to write to non-writeable register {register} - sensor ID {in_sensor_id}")
            return 1

        raw_value = int(int(in_value) / readMultiplier[self.registerDataTypes[register]])

        self.modbusclient.write_single_register(register - 1, raw_value)

        # Make sure we update the raw data and then publish the new value
        self.blockRaw[int((register - 1) / 100)][register % 100 - 1] = raw_value

        self.publishValue(int(in_sensor_id))


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
f_handler = logging.FileHandler("/var/log/isgmysensors.log")
f_handler.setLevel(logging.DEBUG)
f_format = logging.Formatter("%(asctime)s:%(levelname)s: %(message)s")
f_handler.setFormatter(f_format)
logger.addHandler(f_handler)

logger.info("ISG Reader started")


ISG = ISGReader('isgmodbus.cfg')

#print(ISG)
#print(ISG.registerNameValue(507))
#print(ISG.registerNameValue(536))
#print(ISG.registerNameValue(2501))
#print(ISG.registerNameValue(3515))
#print(ISG.sensorRefresh)

time_to_publish = {}

for sensor in ISG.sensorList():

    previous_time = time.time() - 1

    # This ensures every sensor is published straight away
    time_to_publish[sensor] = previous_time

loops = ISG.loops


pause_time = 0

while loops != 0:
    logger.debug(f"In loop waiting for {pause_time} seconds")

    #pauseTime = min(remainingSeconds.values())
    ISG.mqttClient.loop(pause_time)

    current_time = time.time()

    # Publish those that have reached their refresh interval
    for sensor in ISG.sensorIntervals.keys():
        if time_to_publish[sensor] <= current_time:
            ISG.publishValue(sensor)
            time_to_publish[sensor] = int(ISG.sensorIntervals[sensor]) + current_time

    pause_time = min(time_to_publish.values()) - time.time()

    if loops > 0:
        loops -= 1

ISG.closeClient()

