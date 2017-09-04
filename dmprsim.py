#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import ipaddress
import json
import lzma
import math
import os
import random
import shutil
import sys

from datetime import datetime

import core.dmpr
import draw

NO_ROUTER = 100

RTN_MSG_INTERVAL = 30
RTN_MSG_INTERVAL_JITTER = int(RTN_MSG_INTERVAL / 4)
RTN_MSG_HOLD_TIME = RTN_MSG_INTERVAL * 3 + 1

# two stiched images result in 1080p resoltion
SIMU_AREA_X = 960
SIMU_AREA_Y = 1080

DEFAULT_PACKET_TTL = 32

# statitics variables follows
NEIGHBOR_INFO_ACTIVE = 0

PATH_LOGS = "logs"
PATH_IMAGES_RANGE = "images-range"
PATH_IMAGES_TX = "images-tx"
PATH_IMAGES_MERGE = "images-merge"


class ForwardException(Exception): pass

class LoggerClone(core.dmpr.NoOpLogger):
    def __init__(self, directory, id_, loglevel=core.dmpr.NoOpLogger.INFO):
        super(LoggerClone, self).__init__(loglevel)

        try:
            filename = '{0:05}.log'.format(int(id_))
        except ValueError:
            filename = '{}.log'.format(id_)

        os.makedirs(directory, exist_ok=True)
        self._log_fd = open(os.path.join(directory, filename), 'w')

    def log(self, msg, sev, time=lambda: datetime.now().isoformat()):
        if sev < self.loglevel:
            pass
        msg = "{} {}\n".format(time, msg)
        self._log_fd.write(msg)


class Tracer(core.dmpr.NoOpTracer):
    def __init__(self, directory, enable: list=None):
        self.enabled = {}
        if enable is not None:
            for tracer in enable:
                self.enable(tracer)

        os.makedirs(directory, exist_ok=True)
        self.directory = directory

    def enable(self, tracepoint):
        if tracepoint not in self.enabled:
            path = os.path.join(self.directory, tracepoint)
            self.enabled[tracepoint] = open(path, 'w')

    def get_files(self, tracepoint: str) -> list:
        result = []
        for i in self.enabled:
            if tracepoint.startswith(i):
                result.append(self.enabled[i])
        return result

    def log(self, tracepoint, msg, time):
        files = self.get_files(tracepoint)

        for file in files:
            file.write('{} {}\n'.format(time, json.dumps(msg)))


class Router:
    def __init__(self, id_, interfaces, mm, log_directory, msg_compress=False):
        self.id = id_

        logger_dir = os.path.join(log_directory, "logs")
        self.log = LoggerClone(logger_dir, id_)

        tracer_dir = os.path.join(log_directory, "trace")
        self.tracer = Tracer(tracer_dir)

        self.log_directory = log_directory
        self.msg_compress = msg_compress
        self.mm = mm
        self.interfaces = interfaces

        self.routing_table = {}
        self.connections = {}
        self.interface_addr = {}
        self.is_transmitter = False
        self.is_receiver = False
        self.time = 0
        self.routers = []
        self.transmission_within_second = False
        self.forwarded_packets = list()

        self.gen_own_networks()

        for interface in interfaces:
            self.connections[interface['name']] = dict()
            self.interface_addr[interface['name']] = dict()
            self.interface_addr[interface['name']]['v4'] = self._rand_ip_addr(
                "v4")
            self.interface_addr[interface['name']]['v6'] = self._rand_ip_addr(
                "v6")

        self._setup_core()

    def _setup_core(self):
        self._core = core.dmpr.DMPR(log=self.log, tracer=self.tracer)

        self._core.register_routing_table_update_cb(
            self.routing_table_update_cb)
        self._core.register_msg_tx_cb(self.msg_tx_cb)
        self._core.register_get_time_cb(self.get_time)

        conf = self._gen_configuration()
        self._conf = conf
        self._core.register_configuration(conf)
        self._core.register_policy(core.dmpr.SimpleBandwidthPolicy())
        self._core.register_policy(core.dmpr.SimpleLossPolicy())

    def gen_own_networks(self):
        self.networks = list()
        for i in range(2):
            self.networks.append(self._rand_ip_prefix("v4"))

    def pick_random_configured_network(self):
        return self.networks[0][0]

    def get_router_by_interface_addr(self, addr):
        for router in self.routers:
            for iface_name, iface_data in router.interface_addr.items():
                if iface_data['v4'] == addr:
                    return router

    def _generate_configuration(self):
        c = dict()
        c["id"] = self.id
        c["rtn-msg-interval"] = 30
        c["rtn-msg-interval-jitter"] = 7
        c["rtn-msg-hold-time"] = 90

        c["mcast-v4-tx-addr"] = "224.0.1.1"
        c["mcast-v6-tx-addr"] = "ff05:0:0:0:0:0:0:2"

        c["interfaces"] = list()
        for interface in self.interfaces:
            entry = dict()
            entry["name"] = interface["name"]
            entry["addr-v4"] = self.interface_addr[interface['name']]['v4']
            entry["addr-v6"] = self.interface_addr[interface['name']]['v6']

            entry["link-attributes"] = dict()
            characteristics = ("bandwidth", "loss")
            for characteristic in characteristics:
                if characteristic in interface:
                    entry["link-attributes"][characteristic] = interface[
                        characteristic]
            c["interfaces"].append(entry)

        c["networks"] = list()
        for ip in self.networks:
            entry = dict()
            entry["proto"] = "v4"
            entry["prefix"] = ip[0]
            entry["prefix-len"] = ip[1]
            c["networks"].append(entry)
        return c

    def _dump_config(self, config):
        filename = os.path.join(self.log_directory, 'config')
        with open(filename, 'w') as file:
            file.write(json.dumps(config, sort_keys=True,
                                indent=4, separators=(',', ': ')))

    def _gen_configuration(self):
        conf = self._generate_configuration()
        self._dump_config(conf)
        return conf

    def routing_table_update_cb(self, routing_table):
        """ this function is called when core stated
        that the routing table should be updated
        """
        self.log.info("routing table update")
        self.routing_table = routing_table

    def _route_lookup(self, packet):
        tos = packet['tos']  # e.g. "lowest-loss"
        if not tos in self.routing_table:
            print("no policy routing table named: {}".format(tos))
            raise ForwardException("wrong tos")

        dst_prefix = packet['dst-prefix']

        specific_table = self.routing_table[tos]
        for entry in specific_table:
            if entry['proto'] != "v4":
                continue
            if entry['prefix-len'] != "24":
                raise ForwardException(
                    "prefixlen != 24, this is not allowed for the simulation")

            if entry['prefix'] == dst_prefix:
                router = self.get_router_by_interface_addr(entry['next-hop'])
                if router.id not in self.connections[entry['interface']]:
                    raise ForwardException("Router is not connected")
                return router

        raise ForwardException("no route entry")

    def _data_packet_reached_dst(self, packet):
        dst_prefix = packet['dst-prefix']
        for addr in self.networks:
            if addr[0] == dst_prefix:
                return True
        return False

    def forward_packet(self, packet):
        if packet['ttl'] <= 0:
            self.log.info('drop packet, ttl 0')
            return

        if self._data_packet_reached_dst(packet):
            hops = DEFAULT_PACKET_TTL - packet['ttl']
            print("packet reached destination with {} hops".format(hops))
            return

        packet['ttl'] -= 1
        packet['path'].append(self.id)

        try:
            router = self._route_lookup(packet)
        except ForwardException as e:
            print("route lookup failed, drop packet, no next hop\n{}".format(e))
            print(packet['path'])
            return

        print("forward [{:10}] {:>4} -> {:>4}".format(packet['tos'], self.id,
                                                      router.id))
        self.forwarded_packets.append([packet['tos'], self, router])
        router.forward_packet(packet)

    def _msg_compress(self, msg):
        msg_bin = msg.encode("ascii", "ignore")
        msg_comp = lzma.compress(msg_bin)
        return msg_comp

    def _msg_decompress(self, msg):
        msg_bin = lzma.decompress(msg)
        msg_str = msg_bin.decode('ascii')
        return msg_str

    def msg_tx_cb(self, interface_name, proto, dst_mcast_addr, msg):
        self.transmission_within_second = True
        # print(pprint.pformat(msg))
        msg = json.dumps(msg)
        # print("message size: {} bytes (uncompressed)".format(len(msg_json)))
        if self.msg_compress:
            msg = self._msg_compress(msg)
            # print("message size: {} bytes (compressed)".format(len(msg)))
        """ this function is called when core stated
        that a routing message must be transmitted
        """
        emsg = "msg transmission [interface:{}, proto:{}, addr:{}]"
        self.log.info(emsg.format(interface_name, proto, dst_mcast_addr),
                      time=self.get_time())
        # send message to all connected routers
        for r_id, r_obj in self.connections[interface_name].items():
            r_obj.msg_rx(interface_name, msg)

    def msg_rx(self, interface_name, msg):
        if self.msg_compress:
            msg = self._msg_decompress(msg)
        msg_dict = json.loads(msg)
        self._core.msg_rx(interface_name, msg_dict)

    def register_routers(self, r):
        self.routers = r

    def get_time(self):
        return self.time

    def step(self, time):
        # new round, reset to no transmission
        self.transmission_within_second = False
        self.time = time
        self.mm.step()
        self.connect()
        self._core.tick()

    def start(self, time):
        self.time = time
        self._core.start()

    def stop(self):
        self._core.stop()

    def coordinates(self):
        return self.mm.coordinates()

    def connect_links(self, dist, other):
        for interface in self.interfaces:
            name = interface['name']
            range = interface['range']
            if dist <= range:
                self.connections[name][other.id] = other
            else:
                if other.id in self.connections[name]:
                    del self.connections[name][other.id]

    def connect(self):
        for neighbor in self.routers:
            if self.id == neighbor.id:
                continue
            own_cor = self.coordinates()
            other_cor = neighbor.coordinates()
            dist = math.hypot(own_cor[1] - other_cor[1],
                              own_cor[0] - other_cor[0])
            self.connect_links(dist, neighbor)

    def _rand_ip_prefix(self, type_):
        addr = self._rand_ip_addr(type_)
        if type_ == "v4":
            network = ipaddress.IPv4Network(addr+'/24', strict=False)
            return str(network.network_address), 24
        if type_ == "v6":
            network = ipaddress.IPv6Network(addr+'/64', strict=False)
            return str(network.network_address), 64
        raise Exception("only IPv4/IPv6 supported")

    def _rand_ip_addr(self, type_):
        if type_ == "v4":
            return str(ipaddress.IPv4Address(random.randint(0, 2**32)))
        if type_ == "v6":
            return str(ipaddress.IPv6Address(random.randint(0, 2**128)))
        raise Exception("only IPv4/IPv6 supported")


def gen_data_packet(src_id, dst_ip, tos='lowest-loss'):
    return {
        'src-router': src_id,
        'dst-prefix': dst_ip,
        'ttl': DEFAULT_PACKET_TTL,
        'tos': tos,
        'path': []
    }


def setup_log_folder(scenario_name):
    ld = os.path.join("run-data", scenario_name, "logs")
    if os.path.exists(ld):
        shutil.rmtree(ld)
    os.makedirs(ld)


class MobilityArea(object):
    def __init__(self, width, height):
        self.x = width
        self.y = height


class StaticMobilityModel(object):
    def __init__(self, area, x=None, y=None):
        self.area = area
        self.x = x
        self.y = y
        if x is None:
            self.x = random.randint(0, self.area.x)
        if y is None:
            self.y = random.randint(0, self.area.y)
        assert (self.x >= 0 and self.x <= self.area.x)
        assert (self.y >= 0 and self.y <= self.area.y)

    def coordinates(self):
        return self.x, self.y

    def step(self):
        # static, nothing
        pass


class MobilityModel(object):
    LEFT = 1
    RIGHT = 2
    UPWARDS = 1
    DOWNWARDS = 2

    def __init__(self, area):
        self.area = area
        self.direction_x = random.randint(0, 2)
        self.direction_y = random.randint(0, 2)
        self.velocity = 1/random.randint(5, 100)
        self.x = random.randint(0, self.area.x)
        self.y = random.randint(0, self.area.y)

    def _move_x(self, x):
        if self.direction_x == MobilityModel.LEFT:
            x -= self.velocity
            if x <= 0:
                self.direction_x = MobilityModel.RIGHT
                x = 0
        elif self.direction_x == MobilityModel.RIGHT:
            x += self.velocity
            if x >= self.area.x:
                self.direction_x = MobilityModel.LEFT
                x = self.area.x
        else:
            pass
        return x

    def _move_y(self, y):
        if self.direction_y == MobilityModel.DOWNWARDS:
            y += self.velocity
            if y >= self.area.y:
                self.direction_y = MobilityModel.UPWARDS
                y = self.area.y
        elif self.direction_y == MobilityModel.UPWARDS:
            y -= self.velocity
            if y <= 0:
                self.direction_y = MobilityModel.DOWNWARDS
                y = 0
        else:
            pass
        return y

    def move(self, x, y):
        x = self._move_x(x)
        y = self._move_y(y)
        return x, y

    def step(self):
        self.x, self.y = self.move(self.x, self.y)

    def coordinates(self):
        return self.x, self.y
