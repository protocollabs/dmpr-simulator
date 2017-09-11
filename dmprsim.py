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
import core.dmpr.path
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


class JSONPathEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, core.dmpr.path.Path):
            return '>'.join(o.nodes)
        return json.JSONEncoder.default(self, o)


class Tracer(core.dmpr.NoOpTracer):
    def __init__(self, directory, enable: list = None):
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
            file.write('{} {}\n'.format(time, json.dumps(msg, sort_keys=True,
                                                         cls=JSONPathEncoder)))


class Router:
    def __init__(self, id_, interfaces: list, mm,
                 log_directory: str, override_config={}, policies=None):
        self.id = id_

        logger_dir = os.path.join(log_directory, "logs")
        self.log = LoggerClone(logger_dir, id_)

        tracer_dir = os.path.join(log_directory, "trace")
        self.tracer = Tracer(tracer_dir)

        self.log_directory = log_directory
        self.mm = mm
        self.interfaces = interfaces
        self.override_config = override_config

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

        self.policies = policies
        if policies is None:
            self.policies = (core.dmpr.SimpleBandwidthPolicy(),
                             core.dmpr.SimpleLossPolicy())

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
        for policy in self.policies:
            self._core.register_policy(policy)

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

        c.update(self.override_config)
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

    def msg_tx_cb(self, interface_name, proto, dst_mcast_addr, msg):
        """ this function is called when core stated
                that a routing message must be transmitted
                """
        self.transmission_within_second = True
        msg_json = json.dumps(msg)

        emsg = "msg transmission [interface:{}, proto:{}, addr:{}]"
        self.log.info(emsg.format(interface_name, proto, dst_mcast_addr),
                      time=self.get_time())
        # send message to all connected routers
        for r_obj in self.connections[interface_name].values():
            r_obj.msg_rx(interface_name, msg_json)

    def msg_rx(self, interface_name, msg):
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

    def connect(self):
        self.connections = {interface['name']: {} for interface in
                            self.interfaces}
        if not self.mm.visible:
            return
        for neighbor in self.routers:
            if self.id == neighbor.id:
                continue
            if not neighbor.mm.visible:
                continue
            own_cor = self.coordinates()
            other_cor = neighbor.coordinates()
            dist = math.hypot(own_cor[1] - other_cor[1],
                              own_cor[0] - other_cor[0])
            self.connect_links(dist, neighbor)

    def _rand_ip_prefix(self, type_):
        addr = self._rand_ip_addr(type_)
        if type_ == "v4":
            network = ipaddress.IPv4Network(addr + '/24', strict=False)
            return str(network.network_address), 24
        if type_ == "v6":
            network = ipaddress.IPv6Network(addr + '/64', strict=False)
            return str(network.network_address), 64
        raise Exception("only IPv4/IPv6 supported")

    def _rand_ip_addr(self, type_):
        if type_ == "v4":
            return str(ipaddress.IPv4Address(random.randint(0, 2 ** 32)))
        if type_ == "v6":
            return str(ipaddress.IPv6Address(random.randint(0, 2 ** 128)))
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


class MobilityModel(object):
    def __init__(self, area, x=None, y=None, velocity=lambda: 0,
                 disappearance_pattern=(0, 0, 0)):
        self.area = area
        self.velocity = (velocity(), velocity())

        if x is None:
            self.x = random.randint(0, self.area.x)
        else:
            self.x = x
        if y is None:
            self.y = random.randint(0, self.area.y)
        else:
            self.y = y

        if random.random() < disappearance_pattern[0]:
            self.disappear = disappearance_pattern[1:]
        else:
            self.disappear = False
        self.visible = True

    def step(self):
        self.toggle_visibility()
        v_x, v_y = self.velocity
        self.x += v_x
        self.y += v_y

        if self.x not in range(self.area.x):
            v_x = -v_x

        if self.y not in range(self.area.y):
            v_y = -v_y

        self.velocity = v_x, v_y

    def toggle_visibility(self):
        if self.disappear:
            if self.visible:
                self.visible = random.random() > self.disappear[0]
            else:
                self.visible = random.random() < self.disappear[1]

    def coordinates(self):
        return self.x, self.y
