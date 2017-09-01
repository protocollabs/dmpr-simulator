#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import json
import lzma
import math
import os
import random
import shutil
import socket
import struct
import sys
import uuid

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


class LoggerClone(core.dmpr.NoOpLogger):
    def __init__(self, directory, id_, loglevel=core.dmpr.NoOpLogger.INFO):
        super(LoggerClone, self).__init__(loglevel)

        try:
            filename = '{0:05}.log'.format(int(id_))
        except ValueError:
            filename = '{}.log'.format(id_)

        self._log_fd = open(os.path.join(directory, filename), 'w')

    def log(self, msg, sev, time=lambda: datetime.now().isoformat()):
        if sev < self.loglevel:
            pass
        msg = "{} {}\n".format(time, msg)
        self._log_fd.write(msg)


class Tracer(core.dmpr.NoOpTracer):
    def __init__(self, directory, enabled:dict=None):
        if enabled is None:
            self.enabled = {}
        else:
            self.enabled = enabled
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

    def log(self, tracepoint, time, msg):
        files = self.get_files(tracepoint)

        for file in files:
            file.write('{} {}\n'.format(time, msg))


class Router:
    def __init__(self, args, id_, interfaces=None, mm=None, log_directory=None,
                 msg_compress=True):
        self.args = args
        self.id = id_
        self.log = LoggerClone(os.path.join(log_directory, "logs"), id_)
        self.tracer = Tracer(os.path.join(log_directory, 'trace'))
        self._log_directory = log_directory
        self._do_msg_compress = msg_compress
        assert (mm)
        self.mm = mm
        assert (interfaces)
        self._routing_table = {}
        self.interfaces = interfaces
        self.connections = dict()
        self.interface_addr = dict()
        self.is_transmitter = False
        self.is_receiver = False
        self._time = 0
        self._gen_own_networks()
        for interface in self.interfaces:
            self.connections[interface['name']] = dict()
            self.interface_addr[interface['name']] = dict()
            self.interface_addr[interface['name']]['v4'] = self._rand_ip_addr(
                "v4")
            self.interface_addr[interface['name']]['v6'] = self._rand_ip_addr(
                "v6")

        self.transmission_within_second = False
        self.forwarded_packets = list()

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

    def _gen_own_networks(self):
        self._own_networks_v4 = list()
        for i in range(2):
            self._own_networks_v4.append(self._rand_ip_prefix("v4"))

    def pick_random_configured_network(self):
        return self._own_networks_v4[0][0]

    def get_router_by_interface_addr(self, addr):
        for router in self.r:
            for iface_name, iface_data in router.interface_addr.items():
                if iface_data['v4'] == addr:
                    return router
        return None

    def _generate_configuration(self):
        c = dict()
        c["id"] = self.id
        c["rtn-msg-interval"] = 30
        c["rtn-msg-interval-jitter"] = 7
        c["rtn-msg-hold-time"] = 90

        c["mcast-v4-tx-addr"] = "224.0.1.1"
        c["mcast-v6-tx-addr"] = "ff05:0:0:0:0:0:0:2"
        c["proto-transport-enable"] = ["v4"]

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
        for ip in self._own_networks_v4:
            entry = dict()
            entry["proto"] = "v4"
            entry["prefix"] = ip[0]
            entry["prefix-len"] = ip[1]
            c["networks"].append(entry)
        return c

    def _dump_config(self, config):
        dir_ = os.path.join(self._log_directory, "configs")
        if not os.path.exists(dir_):
            os.makedirs(dir_)
        fn = os.path.join(dir_, self.id)
        with open(fn, 'w') as fd:
            fd.write("\n" * 2)
            fd.write(json.dumps(config, sort_keys=True,
                                indent=4, separators=(',', ': ')))
            fd.write("\n" * 3)

    def _gen_configuration(self):
        conf = self._generate_configuration()
        self._dump_config(conf)
        return conf

    def routing_table_update_cb(self, routing_table, priv_data=None):
        """ this function is called when core stated
        that the routing table should be updated
        """
        self.log.info("routing table update")
        self._routing_table = routing_table

    def _ip_addr_to_prefix(self, ip_addr):
        ip_tuple = ip_addr.split(".")
        return "{}.{}.{}.0".format(ip_tuple[0], ip_tuple[1], ip_tuple[2])

    def _route_lookup(self, packet):
        tos = packet['tos']  # e.g. "lowest-lost"
        dst_ip = packet['ip-dst']
        dst_ip_normalized = self._ip_addr_to_prefix(dst_ip)
        if not tos in self._routing_table:
            print("no policy routing table named: {}".format(tos))
            print("ICMP, no route to host or take default path?")
            return False, None, None
        specific_table = self._routing_table[tos]
        for entry in specific_table:
            if entry['proto'] != "v4":
                print("not ipv4, skipping")
                continue
            if entry['prefix-len'] != "24":
                raise Exception(
                    "prefixlen != 24, this is not allowed for the simulation")
            if entry['prefix'] == dst_ip_normalized:
                return True, entry['next-hop'], entry['interface']
        return False, None, None

    def _data_packet_forward(self, packet):
        """ this is a toy version of a forwarding algorithm.
        A first match algorithm because we make sure that no
        other network is available in a simulation with the
        same root"""
        ok, next_hop_ip, interface_name = self._route_lookup(packet)
        if not ok:
            print("route lookup failed, drop packet, no next hop")
            return
        r = self.get_router_by_interface_addr(next_hop_ip)
        if not r:
            print("fck")
            return
        print("forward [{:10}] {:>4} -> {:>4}".format(packet['tos'], self.id,
                                                      r.id))
        self.forwarded_packets.append([packet['tos'], self, r])
        r.data_packet_rx(packet, interface_name)

    def _data_packet_update_ttl(self, packet):
        if packet['ttl'] <= 0:
            print("ttl is 0, drop packet")
            return False
        packet['ttl'] -= 1
        return True

    def _data_packet_reached_dst(self, packet):
        dst_ip = packet['ip-dst']
        dst_ip_prefix = self._ip_addr_to_prefix(dst_ip)
        for addr in self._own_networks_v4:
            if addr[0] == dst_ip_prefix:
                return True
        return False

    def data_packet_rx(self, packet, interface):
        """ received from a neighbor """
        ok = self._data_packet_update_ttl(packet)
        if not ok:
            return
        if self._data_packet_reached_dst(packet):
            hops = DEFAULT_PACKET_TTL - packet['ttl']
            print("packet reached destination with {} hops".format(hops))
            return
        self._data_packet_forward(packet)

    def _msg_compress(self, msg):
        msg_bin = msg.encode("ascii", "ignore")
        msg_comp = lzma.compress(msg_bin)
        return msg_comp

    def _msg_decompress(self, msg):
        msg_bin = lzma.decompress(msg)
        msg_str = msg_bin.decode('ascii')
        return msg_str

    def msg_tx_cb(self, interface_name, proto, dst_mcast_addr, msg,
                  priv_data=None):
        self.transmission_within_second = True
        # print(pprint.pformat(msg))
        msg_json = json.dumps(msg)
        # print("message size: {} bytes (uncompressed)".format(len(msg_json)))
        if self._do_msg_compress:
            msg = self._msg_compress(msg_json)
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
        if self._do_msg_compress:
            msg = self._msg_decompress(msg)
        msg_dict = json.loads(msg)
        self._core.msg_rx(interface_name, msg_dict)

    def register_router(self, r):
        self.r = r

    def get_time(self, priv_data=None):
        return self._time

    def step(self, time):
        # new round, reset to no transmission
        self.transmission_within_second = False
        self._time = time
        self.mm.step()
        self.connect()
        self._core.tick()

    def start(self, time):
        self._time = time
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
        for neighbor in self.r:
            if self.id == neighbor.id:
                continue
            own_cor = self.coordinates()
            other_cor = neighbor.coordinates()
            dist = math.hypot(own_cor[1] - other_cor[1],
                              own_cor[0] - other_cor[0])
            self.connect_links(dist, neighbor)

    def _rand_ip_prefix(self, type_):
        if type_ == "v4":
            addr = random.randint(0, 4000000000)
            a = socket.inet_ntoa(struct.pack("!I", addr))
            b = a.split(".")
            c = "{}.{}.{}.0".format(b[0], b[1], b[2])
            return c, 24
        if type_ == "v6":
            addr = ':'.join(
                '{:x}'.format(random.randint(0, 2 ** 16 - 1)) for i in range(4))
            addr += "::"
            return addr, 64
        raise Exception("only IPv4/IPv6 supported")

    def _rand_ip_addr(self, type_):
        if type_ == "v4":
            addr = random.randint(0, 4000000000)
            a = socket.inet_ntoa(struct.pack("!I", addr))
            b = a.split(".")
            c = "{}.{}.{}.{}".format(b[0], b[1], b[2], b[3])
            return c
        if type_ == "v6":
            return ':'.join(
                '{:x}'.format(random.randint(0, 2 ** 16 - 1)) for i in range(8))
        raise Exception("only IPv4/IPv6 supported")

    def _id_generator(self):
        return str(uuid.uuid1())


def gen_data_packet(src_id, dst_id, tos='lowest-loss'):
    packet = dict()
    packet['ip-src'] = src_id
    packet['ip-dst'] = dst_id
    packet['ttl'] = DEFAULT_PACKET_TTL
    packet['tos'] = tos
    return packet


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
    def __init__(self, area, x, y):
        self.area = area
        self.x = x
        self.y = y
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
        self.velocity = random.randint(1, 1)
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


def two_router_static_in_range(args):
    ld = os.path.join("run-data", args.topology)

    interfaces = [
        {"name": "wifi0", "range": 200, "bandwidth": 8000, "loss": 10},
        {"name": "tetra0", "range": 350, "bandwidth": 1000, "loss": 5}
    ]

    area = MobilityArea(600, 500)
    r = []
    mm = StaticMobilityModel(area, 200, 250)
    r.append(Router(args, "1", interfaces=interfaces, mm=mm, log_directory=ld))
    mm = StaticMobilityModel(area, 400, 250)
    r.append(Router(args, "2", interfaces=interfaces, mm=mm, log_directory=ld))

    r[0].register_router(r)
    r[1].register_router(r)

    r[0].connect()
    r[1].connect()

    r[0].start(0)
    r[1].start(0)

    SIMU_TIME = 1000
    for sec in range(SIMU_TIME):
        sep = '=' * 50
        print("\n{}\nsimulation time:{:6}/{}\n".format(sep, sec, SIMU_TIME))
        for i in range(len(r)):
            r[i].step(sec)
        draw.draw_images(args, ld, area, r, sec)


        # src_id = random.randint(0, NO_ROUTER - 1)
        # dst_id = random.randint(0, NO_ROUTER - 1)
        # packet_low_loss       = gen_data_packet(src_id, dst_id, tos='low-loss')
        # packet_high_througput = gen_data_packet(src_id, dst_id, tos='high-throughput')
        # for sec in range(SIMULATION_TIME_SEC):
        #    for i in range(NO_ROUTER):
        #        r[i].step()
        #    dist_update_all(r)
        #    draw_images(args, r, sec)
        #    # inject test data packet into network
        #    r[src_id].forward_data_packet(packet_low_loss)
        #    r[src_id].forward_data_packet(packet_high_througput)


def two_hundr_router_static_in_range(args):
    ld = os.path.join("run-data", args.topology)

    interfaces = [
        {"name": "wifi0", "range": 200, "bandwidth": 8000, "loss": 10},
        {"name": "tetra0", "range": 350, "bandwidth": 1000, "loss": 5}
    ]

    area = MobilityArea(960, 540)
    r = []
    no_routers = 20
    for i in range(no_routers):
        x = random.randint(200, 400)
        y = random.randint(200, 300)
        mm = StaticMobilityModel(area, x, y)
        r.append(Router(args, str(i), interfaces=interfaces, mm=mm,
                        log_directory=ld))
        r[i].register_router(r)
        r[i].connect()
        r[i].start(0)

    SIMU_TIME = 1000
    for sec in range(SIMU_TIME):
        sep = '=' * 50
        print("\n{}\nsimulation time:{:6}/{}\n".format(sep, sec, SIMU_TIME))
        for i in range(len(r)):
            r[i].step(sec)
        draw.draw_images(args, ld, area, r, sec)


def three_20_router_dynamic(args):
    simulation_time = 100
    if args.simulation_time:
        simulation_time = args.simulation_time
    no_routers = 200
    if args.no_router:
        no_routers = args.no_router
    print("number of simulated router: {}".format(no_routers))

    ld = os.path.join("run-data", args.topology)

    interfaces = [
        {"name": "wifi0", "range": 100, "bandwidth": 8000, "loss": 10},
        {"name": "tetra0", "range": 200, "bandwidth": 1000, "loss": 5}
    ]

    area = MobilityArea(960, 1080)
    r = []
    for i in range(no_routers):
        x = random.randint(200, 400)
        y = random.randint(200, 300)
        mm = MobilityModel(area)
        r.append(Router(args, str(i), interfaces=interfaces, mm=mm,
                        log_directory=ld))
        r[i].register_router(r)
        r[i].connect()
        r[i].start(0)

    src_id = random.randint(0, no_routers - 1)
    r[src_id].is_transmitter = True
    dst_id = random.randint(0, no_routers - 1)
    r[dst_id].is_receiver = True
    dst_ip = r[dst_id].pick_random_configured_network()
    for sec in range(simulation_time):
        sep = '=' * 50
        print(
            "\n{}\nsimulation time:{:6}/{}\n".format(sep, sec, simulation_time))
        for i in range(len(r)):
            r[i].step(sec)
        draw.draw_images(args, ld, area, r, sec)
        packet_low_loss = gen_data_packet(src_id, dst_ip, tos='lowest-loss')
        r[src_id]._data_packet_forward(packet_low_loss)
        packet_high_througput = gen_data_packet(src_id, dst_ip,
                                                tos='highest-bandwidth')
        r[src_id]._data_packet_forward(packet_high_througput)


scenarios = [
    ["001-two-router-static-in-range", two_router_static_in_range],
    ["002-20-router-static-in-range", two_hundr_router_static_in_range],
    ["003-20-router-dynamic", three_20_router_dynamic]
]


def die():
    print("scenario as argument required")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--topology", help="topology", type=str,
                        default=None)
    parser.add_argument("-s", "--simulation-time", help="topology", type=int,
                        default=200)
    parser.add_argument("-l", "--enable-logs", help="enable logging",
                        action='store_true', default=False)
    parser.add_argument("-S", "--set-static-seed", help="set static seed",
                        action='store_true', default=False)
    parser.add_argument("-c", "--color-scheme",
                        help="color scheme: light or dark", type=str,
                        default="dark")
    parser.add_argument("-n", "--no-router",
                        help="number of router, overwrite default", type=int,
                        default=0)
    args = parser.parse_args()
    if not args.topology:
        print(
            "--topology required, please specify a valid file path, exiting now")
        for scenario in scenarios:
            print("  {}".format(scenario[0]))
        sys.exit(1)
    if args.set_static_seed:
        print("initialize seed with 1")
        random.seed(1)
    print("capture logs: {}".format(args.enable_logs))

    return args


def main():
    args = parse_args()

    for scenario in scenarios:
        if args.topology == scenario[0]:
            draw.setup_img_folder(scenario[0])
            setup_log_folder(scenario[0])
            scenario[1](args)
            cmd = "ffmpeg -framerate 10 -pattern_type glob -i "
            cmd += "'run-data/{}/images-range-tx-merge/*.png' ".format(
                scenario[0])
            cmd += "-c:v libx264 -pix_fmt yuv420p dmpr.mp4"
            print("now execute \"{}\" to generate a video".format(cmd))
            sys.exit(0)
    die()


if __name__ == '__main__':
    main()
