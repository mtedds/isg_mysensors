#
# This contains all of the modbus related functionality
#
from datetime import datetime, timedelta
import requests
from isg_mysensors_constants import *


class http:
    def __init__(self, in_host, in_logger):
        in_logger.debug(f"http __init__ {in_host}")

        self.logger = in_logger
        self.host = in_host

        self.block_raw = {}
        self.block_page = {1: "?s=3,0", 2: "?s=3,1"}
        self.block_start = {1: 130, 2: 172}
        self.block_length = {1: 21, 2: 21}
        self.refresh_datetime = {}
        self.register_values = {}

        # This can be run here as we don't need to read anything from the config
        self.build_blocks()

    # Note that http blocks are linked to pages
    # In the page text they are "valNNN" and NNN is used as the register number
    def build_blocks(self):
        self.logger.debug(f"http build_blocks")

        for cur_block in self.block_start.keys():
            self.refresh_datetime[cur_block] = datetime.min  # Set as old as possible so always refreshed on first read

    def get_block(self, in_register):
        block = -1
        for cur_block in self.block_start.keys():
            if ((in_register >= self.block_start[cur_block]) and
                    (in_register < self.block_start[cur_block] + self.block_length[cur_block])):
                block = cur_block

        if block == -1:
            self.logger.error(f"Tried to read invalid register {in_register}")

        return block

    # Refresh just the block containing the register we are reading
    def refresh_raw_values(self, in_block):
        self.logger.debug(f"http refresh_raw_values {in_block}")

        page = requests.get(f"http://{self.host}/{self.block_page[in_block]}")

        start_val = self.block_start[in_block]

        # These are the lists of on / off pairs for the CH and DHW - 3 pairs per day
        if in_block == 1 or in_block == 2:
            text_pos = 0
            # Walk through the page from start to end looking for appropriate text
            while start_val < self.block_start[in_block] + self.block_length[in_block] - 1:
                text_pos += page.text[text_pos:].find(f'"val{start_val}","val{start_val+1}","val{start_val+2}"') + 27
                text_pos += page.text[text_pos:].find(': [') + 3
                end_bracket = text_pos + page.text[text_pos:].find(']')
                # Finally reached the values themselves!!!
                values = page.text[text_pos:end_bracket].split(",")
                # Replace empty values with 128, which is recognised as empty by ISG
                if len(values) < 2:
                    self.block_raw[start_val] = [128, 128]
                else:
                    self.block_raw[start_val] = [values[0], values[1]]

                if len(values) < 4:
                    self.block_raw[start_val+1] = [128, 128]
                else:
                    self.block_raw[start_val+1] = [values[2], values[3]]

                if len(values) < 6:
                    self.block_raw[start_val+2] = [128, 128]
                else:
                    self.block_raw[start_val+2] = [values[4], values[5]]

                start_val += 3

        self.refresh_datetime[in_block] = datetime.now()

    # Only refresh the raw data if the register raw data is stale
    def refresh_if_needed(self, in_register, in_refresh):
        self.logger.debug(f"http refresh_if_needed {in_register} {in_refresh}")

        block = self.get_block(in_register)

        if datetime.now() > (self.refresh_datetime[block] + timedelta(seconds=int(in_refresh))):
            self.refresh_raw_values(block)

        return block

    def refresh_net_value(self, in_register, in_refresh, in_register_type, in_type):
        self.logger.debug(f"http refresh_net_value {in_register} {in_refresh} {in_register_type} {in_type}")

        block = self.refresh_if_needed(in_register, in_refresh)
        raw_value = self.block_raw[in_register]

        if in_type == 'interval':
            self.register_values[in_register] = f"{[int(raw_value[0]) * 15, int(raw_value[1]) * 15]}"

        return

    def register_value(self, in_register, in_refresh, in_reg_datatype, in_type):
        self.logger.debug(f"http register_value {in_register} {in_refresh} {in_reg_datatype} {in_type}")

        num_reg = int(in_register[3:])
        #        print("registerValue " + str(inRegister) + " " + str(inRefresh))
        self.refresh_net_value(num_reg, in_refresh, in_reg_datatype, in_type)
        return self.register_values[num_reg]

    def write_register(self, in_sensor_id, in_register, in_reg_data_type, in_value):

        # TODO: GOT TO HERE
        self.logger.debug(f"http write_register {in_sensor_id} {in_register} {in_reg_data_type} {in_value}")

        raw_value = int(int(in_value) / readMultiplier[in_reg_data_type])

        # self.modbus_client.write_single_register(in_register - 1, raw_value)

        # Make sure we update the raw data and then publish the new value
        self.block_raw[int((in_register - 1) / 100)][in_register % 100 - 1] = raw_value

        return
