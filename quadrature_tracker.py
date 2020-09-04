#!/usr/bin/env python3
#
# "Spy" satellite tracker
# (C) David Pello for Tabakalera Medialab
# Using pysattracker library: https://github.com/cubehub/pysattracker
# This program is free software under the GNU GPL License:
# https://www.gnu.org/licenses/gpl-3.0.html
#
# This program expects a satdata.py file with an array of dictionaries
# containing satellite data. Dictionary keys are "name", "tle1", "tle2"
# and "freqs" for name, TLE lines and downlink frequencies.
# Then it listens in port 7777 for a satellite name from that array, and
# tracks it if it's visible. For tracking it connects to rotctld to move
# the antenna and to gqrx to adjust frequency.

import socket
import sys
import time
import socketserver
import threading, queue
import atexit

import sattracker
from satdata import sat_data
from trackerconfig import config

# classes
class QRotor:
    def __init__(self):
        # connect to rotctld
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_address = (config["rotctld_addr"], config["rotctld_port"])
        try:
            self.conn.connect(self.server_address)
        except:
            sys.exit("Can't connect to rotctld")
        # try to get info
        try:
            self.conn.sendall(b'_\n')
            data = self.conn.recv(30)
            if len(data) == 0:
                sys.exit("No data received from rotctld")
        except:
            sys.exit("Problem communicating with rotctld", sys.exc_info()[0])
        # we received something, rotctld must be running
        print("Connected to rotctld", file=sys.stderr)
    
    def get_pos(self):
        try:
            self.conn.sendall(b'p\n')
            data = self.conn.recv(256)
            # try to parse the data
            if len(data) > 0:
                # split lines
                return (data.split(b'\n')[0], data.split(b'\n')[1])
            else:
                sys.exit("Problem reading position")
        except:
            sys.exit("Problem reading position from rotctld", sys.exc_info()[0])

    def get_abs_pos(self):
        pos = self.get_pos()
        az = float(pos[0])
        el = float(pos[1])
        if az < 0:
            az = az + 360
        if az > 359:
            az = az - 360
        return (az, el)

    def set_pos(self, az, el):
        try:
            self.conn.sendall(b'P ' + bytes(str(az), "utf-8") + b' ' + bytes(str(el), "utf-8") + b'\n')
            data = self.conn.recv(256)
            # try to get error code
            if len(data) > 0:
                if data.decode("utf-8") == "RPRT 0\n":
                    return True
                else:
                    sys.exit("Problem moving the rotator: " + data.decode("utf-8"))
            else:
                sys.exit("No response from rotctld when setting position")
        except:
            sys.exit("Problem setting position to rotctld")

class QRenderer:
    def __init__(self):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_address = (config["renderer_addr"] , config["renderer_port"])
    def on_pos(self):
        try:
            self.conn.sendto(b"ON POS", self.server_address)
        finally:
            pass


class QGqrx:
    def __init__(self):
        # connect to gqrx
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_address = (config["gqrx_addr1"], config["gqrx_port"])
        try:
            self.conn.connect(self.server_address)
        except:
            sys.exit("Can't connect to Gqrx")
        # try to get info
        try:
            self.conn.sendall(b'_\n')
            data = self.conn.recv(30)
            if len(data) == 0:
                sys.exit("No data received from gqrx")
        except:
            sys.exit("Problem communicating with gqrx: " + str(sys.exc_info()[0]))
        # we received something, gqrx must be running
        print("Connected to gqrx", file=sys.stderr)

    def set_freq(self, freq):
        try:
            self.conn.sendall(b'F ' + bytes(str(freq), "utf-8") + b'\n')
            data = self.conn.recv(256)
            # try to get error code
            if len(data) > 0:
                if data.decode("utf-8") == "RPRT 0\n":
                    return True
                else:
                    sys.exit("Problem setting the frequency: " + data.decode("utf-8"))
            else:
                sys.exit("No response from gqrx when setting frequency")
        except:
            sys.exit("Problem sending frequency to gqrx")

# request handler class
class QTrackerRequest(socketserver.BaseRequestHandler):
    def handle(self):
        while 1:
            data_received = self.request.recv(1024)
            if not data_received: 
                break
            # look for satellite
            sat_name = data_received.decode("utf-8")
            # quit?
            if sat_name.strip() == "EXIT":
                sat_q.put("EXIT")
                sys.exit("EXIT COMMAND")
            # find sat name in list and send to tracker if found
            # empty? 
            if sat_name.strip():
                for sat in sat_data:
                    if sat_name.strip() in sat["name"]:
                        sat_q.put(sat["name"])

    def send_data(data):
        self.request.sendall(data)


class QTracker(threading.Thread):
    def __init__(self, sat_q, result_q):
        super(QTracker, self).__init__()
        self.sat_q = sat_q
        self.result_q = result_q
        self.stoprequest = threading.Event()
        self.tracking = False
        self.sat_name = ""
        self.rotor = QRotor()
        self.gqrx1 = QGqrx()
        self.az = 0
        self.ele = 0
        self.last_az = self.az
        self.last_ele = self.ele
        self.last_name = ""
        print ("Resetting rotor...", file=sys.stderr)
        self.rotor.set_pos(0.0, 0.0)
        while self.rotor.get_abs_pos()[0] != 0.0 or self.rotor.get_abs_pos()[1] != 0.0:
            print(float(self.rotor.get_pos()[0]), float(self.rotor.get_pos()[1]), file=sys.stderr)
            time.sleep(1)
        print ("Rotor at 0, 0")
        self.renderer = QRenderer()

    def update_pos(self):
        self.rotor.set_pos(self.az, self.ele)
        self.last_az = self.az
        self.last_ele = self.ele

    def reached_pos(self):
        if self.az == self.rotor.get_abs_pos()[0] and self.ele == self.rotor.get_abs_pos()[1]:
            if self.sat_name.strip() != self.last_name:
                self.last_name = self.sat_name.strip()
                print("ON POS", file=sys.stderr)
                self.renderer.on_pos()

    def run(self):
        while not self.stoprequest.isSet():
            # get sat name to track
            try:
                self.sat_name = self.sat_q.get(True, 0.5)
                print("REQUESTED: ", self.sat_name, file=sys.stderr)
                if self.sat_name == "EXIT":
                    self.stoprequest.set()
            except queue.Empty:
                # see if we need to track
                if self.sat_name.strip() != "":
                    for sat in sat_data:
                        if self.sat_name.strip() in sat["name"]:
                            self.tracker = sattracker.Tracker(satellite=sat, groundstation=config["location"])
                            self.tracker.set_epoch(time.time())
                            if self.tracker.elevation() > 0.0:
                                self.tracking = True
                                # round values to x.0 - x.5
                                self.ele = round(self.tracker.elevation()*2)/2
                                self.az = round(self.tracker.azimuth()*2)/2
                                # need to update?
                                if self.ele != self.last_ele or self.az != self.last_az:
                                    self.update_pos()
                                    # are we already on postion?
                                    self.reached_pos()

                                    # radio control?
                                    if not "FrequencyPlaceholder" in sat["freqs"].strip() :
                                        try: 
                                            # get first frequency
                                            self.freq = sat["freqs"].strip().split(";")[0].split(" ")[0]
                                            # convert to Hz
                                            self.freq = float(self.freq) * 1000000
                                        except:
                                            # problem, resort to default freq
                                            self.freq = config["default_freq"]
                                    else:
                                        # use default frequency (SATCOM?)
                                        self.freq = config["default_freq"]
                                    # calculate doppler shift
                                    self.freq = self.freq + self.tracker.doppler(self.freq)
                                    self.gqrx1.set_freq(self.freq)
                                    print(self.tracker.satellite.name, self.az, self.ele, self.freq, file=sys.stderr)
                                time.sleep(0.5)
                            else:
                                self.tracking = False


# variables
sat_q = queue.Queue()
result_q = queue.Queue()
tracker_thread = None
tracker_server = None

if __name__ == "__main__":
    try:
        tracker_thread = QTracker(sat_q=sat_q, result_q=result_q)
        tracker_thread.start()

        tracker_server = socketserver.TCPServer(('', config["tracker_port"]), QTrackerRequest)
        print("Created TCP server on port " + str(config["tracker_port"]), file=sys.stderr)
        tracker_server.serve_forever()
    except:
        if tracker_server:
            tracker_server.shutdown()
            tracker_server.server_close()
        if tracker_thread:
            sat_q.put("EXIT")
            tracker_thread.join()
        sys.exit("Exiting main threads: " + str(sys.exc_info()[0]) + " " + str(sys.exc_info()[1]))
