#
# All of the configuration constants / etc for the ISG mysensors daemon

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
register_interval = 'Interval'
sensorRefresh = 'Refresh'
sensorId = 'Sensor id'
sensorType = 'Sensor type'
variableType = 'Variable type'
sensorInterval = 'Publish interval'
sensorPublishTime = 'Publish time'

registerTypes = {
        'read': 1,
        'read/write': 2
        }

# Note that type 2 and 7 are signed
# Types 6 and 8 are unsigned
readMultiplier = {
        2: 0.1,
        6: 1,
        7: 0.01,
        8: 1
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
