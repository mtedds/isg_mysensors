#
# This contains all of the modbus related functionality
#
from easymodbus.modbusClient import ModbusClient
from datetime import datetime, timedelta
import sys
from isg_mysensors_constants import *


class modbus:
    def __init__(self, in_host, in_port, in_logger):
        in_logger.debug(f"modbus __init__ {in_host}, {in_port}")

        self.logger = in_logger

        try:
            self.modbus_client = ModbusClient(in_host, int(in_port))
            self.modbus_client.connect()
        except:
            in_logger.critical("Failed to connect to ISG")
            in_logger.critical(sys.exc_info()[0])
            raise

        self.block_raw = {}
        self.block_start = {}
        self.block_length = {}
        self.refresh_datetime = {}
        self.register_values = {}

    def run_close(self):
        self.logger.debug(f"modbus run_close")
        self.modbus_client.close()

    def build_blocks(self, in_reg_num_list):
        self.logger.debug(f"modbus build_blocks {in_reg_num_list}")
        # Read in from the device in blocks of max 100 in sections 501-600, 2501-2600, etc

        # Build up the block details by reading through the list of registers
        # and breaking when we find a new 100 max grouping
        curBlock = int((int(in_reg_num_list[0]) - 1) / 100)
        self.block_start[curBlock] = int(in_reg_num_list[0])
        self.block_length[curBlock] = 2
        self.refresh_datetime[curBlock] = datetime.min  # Set as old as possible so always refreshed on first read

        for readNum in in_reg_num_list:
            if readNum[0:3] == "val":
                break
            else:
                reg_num = int(readNum)
                if int((reg_num - 1) / 100) == curBlock:
                    self.block_length[curBlock] = reg_num - int(self.block_start[curBlock]) + 2
                else:
                    curBlock = int((reg_num - 1) / 100)
                    self.block_start[curBlock] = reg_num
                    self.block_length[curBlock] = 2
                    self.refresh_datetime[curBlock] = datetime.min

    # Refresh just the block containing the register we are reading
    # Note that the block is the first register value / 100 - eg. 5 = register 500 onwards
    def refresh_raw_values(self, in_block):
        self.logger.debug(f"modbus refresh_raw_values {in_block}")
        # 1500s are read / write holding registers
        try:
            if in_block == 15:
                self.block_raw[in_block] = self.modbus_client.read_holdingregisters(
                                            self.block_start[in_block]-1, self.block_length[in_block])
            else:
                self.block_raw[in_block] = self.modbus_client.read_inputregisters(
                                            self.block_start[in_block]-1, self.block_length[in_block])

            self.refresh_datetime[in_block] = datetime.now()

        except Exception:
            self.logger.error(f"modbus refresh_raw_values failed to read - probably a timeout")
            pass

    # Only refresh the raw data if the register raw data is stale
    def refresh_if_needed(self, in_register, in_refresh):
        self.logger.debug(f"modbus refresh_if_needed {in_register} {in_refresh}")

        block = int((in_register - 1) / 100)
        if datetime.now() > (self.refresh_datetime[block] + timedelta(seconds=int(in_refresh))):
            self.refresh_raw_values(block)

    def refresh_net_value(self, in_register, in_refresh, in_register_type, in_type):
        self.logger.debug(f"modbus refresh_net_value {in_register} {in_refresh} {in_register_type} {in_type}")

        self.refresh_if_needed(in_register, in_refresh)
        raw_value = self.block_raw[int((in_register-1)/100)][in_register - self.block_start[int((in_register-1)/100)]]
        # Handle sign for types 2 and 7
        if (int(raw_value) > 32768) and \
                (in_register_type == 2 or in_register_type == 7):
            net_value = int(raw_value) - 65536
        else:
            net_value = int(raw_value)
        net_value *= readMultiplier[in_register_type]

        if in_type == 'long':
            net_value += self.block_raw[int((in_register-1)/100)]\
                                       [in_register - self.block_start[int((in_register-1)/100)]+1] * 1000

        if readMultiplier[in_register_type] == 1:
            self.register_values[in_register] = int(net_value)
        else:
            self.register_values[in_register] = round(net_value, 2)

        return

    def register_value(self, in_register, in_refresh, in_reg_datatype, in_type):
        self.logger.debug(f"modbus register_value {in_register} {in_refresh} {in_type}")

        #        print("registerValue " + str(inRegister) + " " + str(inRefresh))
        self.refresh_net_value(in_register, in_refresh, in_reg_datatype, in_type)
        return self.register_values[in_register]

    def write_register(self, in_sensor_id, in_register, in_reg_data_type, in_value):
        self.logger.debug(f"modbus write_register {in_sensor_id} {in_register} {in_reg_data_type} {in_value}")

        raw_value = int(float(in_value) / float(readMultiplier[in_reg_data_type]))

        self.modbus_client.write_single_register(in_register - 1, raw_value)

        # Make sure we update the raw data and then publish the new value
        self.block_raw[int((in_register - 1) / 100)][in_register % 100 - 1] = raw_value

        return
