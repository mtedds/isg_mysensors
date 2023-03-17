#
# This contains all of the modbus related functionality
#
from datetime import datetime, timedelta
import requests
import pycurl
from isg_mysensors_constants import *


def to_hhmm(in_minutes):
    hours = f"{int(in_minutes / 60):02d}"
    minutes = f"{in_minutes % 60:02d}"
    return f"{hours}:{minutes}"


class http:
    def __init__(self, in_host, in_logger):
        in_logger.debug(f"http __init__ {in_host}")

        self.logger = in_logger
        self.host = in_host

        # Blocks 1 and 2 are the HC and DHW programmes
        # Initially, these were defined as sensors but now they are loaded to block_raw,
        # serialised in JSON and then sent to the controller in a special message that
        # the controller understands and then writes to the database as a set of external
        # timed triggers so that they can be processed in the same way as the other programmes
        # Note that block 3 is used for the compressor idle time (special case)
        self.block_raw = {}
        self.block_page = {1: "?s=3,0", 2: "?s=3,1", 3: "?s=2,0"}
        # These are the "valNNN" names used in the web pages
        # Note that each entry contains a start time and an end time
        self.block_start = {1: 130, 2: 172, 3: -1}
        self.block_length = {1: 21, 2: 21, 3: 0}
        self.refresh_datetime = {}
        self.register_values = {}

        # This can be run here as we don't need to read anything from the config
        self.build_blocks()

    # Note that http blocks are linked to pages
    # In the page text they are "valNNN" and NNN is used as the register number
    def build_blocks(self):
        self.logger.debug(f"http build_blocks")

        for cur_block in self.block_page.keys():
            self.refresh_datetime[cur_block] = datetime.min  # Set as old as possible so always refreshed on first read

    def get_block(self, in_register):
        self.logger.debug(f"http get_block {in_register}")

        block = -1

        if in_register == "idle":
            return 3

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

        request = f"http://{self.host}/{self.block_page[in_block]}"

        page = requests.get(request, timeout=10)

        while page.status_code != 200:
            self.logger.error(f"http refresh_raw_values - http get failed: {request} {page.status_code} {page.reason}")
            page = requests.get(request, timeout=60)

        start_val = self.block_start[in_block]

        # These are the lists of on / off pairs for the CH and DHW - 3 pairs per day
        if in_block == 1 or in_block == 2:
            text_pos = 0
            # Whilst block_raw is populated (but is probably not used - no need to define sensors)
            # programme will be returned to the caller and then forwarded to the controller in a special message
            day = 0
            programme = {}
            # Walk through the page from start to end looking for appropriate text
            while start_val < self.block_start[in_block] + self.block_length[in_block] - 1:
                programme[day] = {}
                text_pos += page.text[text_pos:].find(
                    f'"val{start_val}","val{start_val + 1}","val{start_val + 2}"') + 27
                text_pos += page.text[text_pos:].find(': [') + 3
                end_bracket = text_pos + page.text[text_pos:].find(']')
                # Finally reached the values themselves!!!
                values = page.text[text_pos:end_bracket].split(",")
                # Replace empty values with 128, which is recognised as empty by ISG
                if len(values) < 2:
                    self.block_raw[start_val] = ["32:00", "32:00"]
                else:
                    self.block_raw[start_val] = [f"{to_hhmm(int(values[0]) * 15)}", f"{to_hhmm(int(values[1]) * 15)}"]
                programme[day][0] = self.block_raw[start_val]

                if len(values) < 4:
                    self.block_raw[start_val + 1] = ["32:00", "32:00"]
                else:
                    self.block_raw[start_val + 1] = [f"{to_hhmm(int(values[2]) * 15)}",
                                                     f"{to_hhmm(int(values[3]) * 15)}"]
                programme[day][1] = self.block_raw[start_val + 1]

                if len(values) < 6:
                    self.block_raw[start_val + 2] = ["32:00", "32:00"]
                else:
                    self.block_raw[start_val + 2] = [f"{to_hhmm(int(values[4]) * 15)}",
                                                     f"{to_hhmm(int(values[5]) * 15)}"]
                programme[day][2] = self.block_raw[start_val + 2]

                start_val += 3
                day += 1

            return programme

        elif in_block == 3:
            text_pos = page.text.find('REMAINING IDLE TIME') + 18
            if text_pos == -1:
                self.block_raw["idle"] = "0min"
            else:
                text_pos += page.text[text_pos:].find('<td class="value round-rightbottom">') + 36
                end_pos = page.text[text_pos:].find('<') + text_pos
                self.block_raw["idle"] = page.text[text_pos:end_pos]

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

        self.refresh_if_needed(in_register, in_refresh)
        raw_value = self.block_raw[in_register]

        if in_type == 'interval':
            self.register_values[in_register] = \
                f"[{to_hhmm(int(raw_value[0]) * 15)}, {to_hhmm(int(raw_value[1]) * 15)}]"
        elif in_type == 'idle':
            self.register_values[in_register] = raw_value.split("min")[0]

        return

    def register_value(self, in_register, in_refresh, in_reg_datatype, in_type):
        self.logger.debug(f"http register_value {in_register} {in_refresh} {in_reg_datatype} {in_type}")

        num_reg = in_register[3:]
        if in_type != "idle":
            num_reg = int(num_reg)

        #        print("registerValue " + str(inRegister) + " " + str(inRefresh))
        self.refresh_net_value(num_reg, in_refresh, in_reg_datatype, in_type)
        return self.register_values[num_reg]

    def write_register(self, in_sensor_val, in_value):

        # TODO: This needs fixing up!
        self.logger.debug(f"http write_register {in_sensor_val} {in_value}")

        # This is the only way I could get this working!
        # I tried using urlencode, various forms of data but only this worked
        # The equivalent curl command line is:
        # curl http://servicewelt/save.php --trace-ascii /dev/stdout --data-urlencode 'data=[{"name":"val22","value":"46.5"}]'
        # (trace turned on!)

        http_connection = pycurl.Curl()
        http_connection.setopt(http_connection.URL, 'http://servicewelt/save.php')
        post_field = f'data=%5B%7B%22name%22%3A%22{in_sensor_val}%22%2C%22value%22%3A%22{in_value}%22%7D%5D'
        self.logger.debug(f"http write_register {post_field}")
        http_connection.setopt(http_connection.POSTFIELDS, post_field)
        http_connection.perform()
        http_connection.close()

        register = int(in_sensor_val[3:])
        block = -1
        for index in self.block_start.keys():
            if self.block_start[index] <= register < self.block_start[index] + self.block_length[index]:
                block = index

        if block > -1:
            # TODO - update the raw data
            # Make sure we update the raw data
            # if register % 2 == 0:
            # self.block_raw[start_val] = ["32:00", "32:00"]
            pass

        return
