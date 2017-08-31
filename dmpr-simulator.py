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

import cairo
from datetime import datetime
from PIL import Image

import core.dmpr

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



class Tracer(object):
    TICK = "TICK"

    def __init__(self, enabled=[]):
        self.enabled = enabled

    def enable(self, enable):
        if enable in self.enabled:
            return
        self.enabled.append(enable)

    def log(self, tracepoint, msg):
        if not tracepoint in self.enabled:
            return
        # XXX: this will print in a specific trace directory
        # in a node specific file with a tracepoint specific
        # file. So really seperated by file. This will allow
        # really easy data analysis. Just open file datafiles
        # you are interested in for the particular nodes.
        print(json.dumps(msg, sort_keys=True))


class Router:
    def __init__(self, args, id_, interfaces=None, mm=None, log_directory=None,
                 msg_compress=True):
        self.args = args
        self.id = id_
        self.log = LoggerClone(args, os.path.join(log_directory, "logs"), id_)
        self.tracer = Tracer()
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
            self.routing_table_update_cb, priv_data=None)
        self._core.register_msg_tx_cb(self.msg_tx_cb, priv_data=None)
        self._core.register_get_time_cb(self.get_time, priv_data=None)

        conf = self._gen_configuration()
        self._conf = conf
        self._core.register_configuration(conf)

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
        c["rtn-msg-interval"] = "30"
        c["rtn-msg-interval-jitter"] = "7"
        c["rtn-msg-hold-time"] = "90"

        c["mcast-v4-tx-addr"] = "224.0.1.1"
        c["mcast-v6-tx-addr"] = "ff05:0:0:0:0:0:0:2"
        c["proto-transport-enable"] = ["v4"]

        c["interfaces"] = list()
        for interface in self.interfaces:
            entry = dict()
            entry["name"] = interface["name"]
            entry["addr-v4"] = self.interface_addr[interface['name']]['v4']
            entry["addr-v6"] = self.interface_addr[interface['name']]['v6']

            entry["link-characteristics"] = dict()
            characteristics = ("bandwidth", "loss")
            for characteristic in characteristics:
                if characteristic in interface:
                    entry["link-characteristics"][characteristic] = interface[
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


def color_links_light(index):
    return (.1, .1, .1, .4)


def color_links_dark(index):
    table = ((1.0, 0.15, 0.15, 1.0), (0.15, 1.0, 0.15, 1.0),
             (0.45, 0.2, 0.15, 1.0), (0.85, 0.5, 0.45, 1.0))
    return table[index]


def color_links(args, index):
    if args.color_scheme == "light":
        return color_links_light(index)
    else:
        return color_links_dark(index)


def color_db_light():
    return (1.000, 1.000, 1.000, 1.0)


def color_db_dark():
    return (0.15, 0.15, 0.15, 1.0)


def color_db(args):
    if args.color_scheme == "light":
        return color_db_light()
    else:
        return color_db_dark()


def color_range_light(index):
    return (1.0, 1.0, 1.0, 0.1)


def color_range_dark(index):
    color = ((1.0, 1.0, 0.5, 0.05), (1.0, 0.0, 1.0, 0.05),
             (0.5, 1.0, 0.0, 0.05), (1.0, 0.5, 1.0, 0.05))
    return color[index]


def color_range(args, index):
    if args.color_scheme == "light":
        return color_range_light(index)
    else:
        return color_range_dark(index)


def color_node_inner_light():
    return (0.1, 0.1, 0.1)


def color_node_inner_dark():
    return (0.5, 1, 0.7)


def color_node_inner(args):
    if args.color_scheme == "light":
        return color_node_inner_light()
    else:
        return color_node_inner_dark()


def color_node_transmitter_outline_light():
    return (1.0, 0.0, 1.0)


def color_node_transmitter_outline_dark():
    return (0.3, 0.5, 0.0)


def color_node_transmitter_outline(args):
    if args.color_scheme == "light":
        return color_node_transmitter_outline_light()
    else:
        return color_node_transmitter_outline_dark()


def color_node_receiver_outline_light():
    return (0.9, .2, .1)


def color_node_receiver_outline_dark():
    return (1.0, 0.0, 1.0)


def color_node_receiver_outline(args):
    if args.color_scheme == "light":
        return color_node_receiver_outline_light()
    else:
        return color_node_receiver_outline_dark()


def color_text_light():
    return (0., 0., 0.)


def color_text_dark():
    return (0.5, 1, 0.7)


def color_text(args):
    if args.color_scheme == "light":
        return color_text_light()
    else:
        return color_text_dark()


def color_text_inverse_light():
    return (1., 1., 1.)


def color_text_inverse_dark():
    return (1, 0, 0)


def color_text_inverse(args):
    if args.color_scheme == "light":
        return color_text_inverse_light()
    else:
        return color_text_inverse_dark()


def draw_router_loc(args, ld, area, r, img_idx):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, area.x, area.y)
    ctx = cairo.Context(surface)
    ctx.rectangle(0, 0, area.x, area.y)
    ctx.set_source_rgba(*color_db(args))
    ctx.fill()

    for i in range(len(r)):
        router = r[i]
        x, y = router.coordinates()

        ctx.set_line_width(0.1)
        path_thinkness = 6.0
        # iterate over links
        interfaces_idx = 0
        for i, t in enumerate(router.interfaces):
            range_ = t['range']
            interface_name = t['name']
            ctx.set_source_rgba(*color_range(args, i))
            ctx.move_to(x, y)
            ctx.arc(x, y, range_, 0, 2 * math.pi)
            ctx.fill()

            # draw lines between links
            ctx.set_line_width(path_thinkness)
            for r_id, r_obj in router.connections[interface_name].items():
                other_x, other_y = r_obj.coordinates()
                ctx.move_to(x, y)
                ctx.set_source_rgba(*color_links(args, interfaces_idx))
                ctx.line_to(other_x, other_y)
                ctx.stroke()
            interfaces_idx += 1
            path_thinkness -= 4.0
            if path_thinkness < 2.0:
                path_thinkness = 2.0

    # draw active links
    ctx.set_line_width(4.0)
    dash_len = 4.0
    for i in range(len(r)):
        for data in r[i].forwarded_packets:
            tos, src, dst = data
            ctx.set_source_rgba(1., 0, 0, 1)
            ctx.set_dash([dash_len, dash_len])
            if tos == "highest-bandwidth":
                ctx.set_source_rgba(0., 0., 1., 1)
                ctx.set_dash([dash_len, dash_len], dash_len)
            s_x, s_y = src.coordinates()
            d_x, d_y = dst.coordinates()
            ctx.move_to(s_x, s_y)
            ctx.line_to(d_x, d_y)
            ctx.stroke()
    # reset now
    for i in range(len(r)):
        r[i].forwarded_packets = list()

    # draw text and node circle
    ctx.set_line_width(3.0)
    for i in range(len(r)):
        router = r[i]
        x, y = router.coordinates()
        # node middle point
        ctx.move_to(x, y)
        ctx.arc(x, y, 5, 0, 2 * math.pi)

        if router.is_transmitter:
            ctx.set_source_rgb(*color_node_transmitter_outline(args))
            ctx.stroke_preserve()

            ctx.set_source_rgb(*color_text_inverse(args))
            ctx.move_to(x + 11, y - 9)
            ctx.set_antialias(False)
            ctx.show_text("Transmitter")
            ctx.set_antialias(True)

            ctx.set_source_rgb(*color_node_transmitter_outline(args))
            ctx.move_to(x + 10, y - 10)
            ctx.set_antialias(False)
            ctx.show_text("Transmitter")
            ctx.set_antialias(True)

        if router.is_receiver:
            # draw circle outline
            ctx.set_source_rgb(*color_node_receiver_outline(args))
            ctx.stroke_preserve()

            ctx.set_source_rgb(*color_text_inverse(args))
            ctx.move_to(x + 11, y - 9)
            ctx.set_antialias(False)
            ctx.show_text("Receiver")
            ctx.set_antialias(True)

            # show text
            ctx.set_source_rgb(*color_node_receiver_outline(args))
            ctx.move_to(x + 10, y - 10)
            ctx.set_antialias(False)
            ctx.show_text("Receiver")
            ctx.set_antialias(True)

        ctx.set_source_rgb(*color_node_inner(args))
        ctx.fill()
        # show router id, first we draw a background
        # with a little offset and the inverse color,
        # later we draw the actual text
        ctx.set_font_size(10)
        ctx.set_source_rgb(*color_text_inverse(args))
        ctx.move_to(x + 10 + 1, y + 10 + 1)
        ctx.show_text(str(router.id))
        ctx.set_source_rgb(*color_text(args))
        ctx.move_to(x + 10, y + 10)
        ctx.set_antialias(False)
        ctx.show_text(str(router.id))
        ctx.set_antialias(True)

    full_path = os.path.join(ld, "images-range", "{0:05}.png".format(img_idx))
    surface.write_to_png(full_path)


def color_transmission_circle_light():
    return (0., .0, .0, .2)


def color_transmission_circle_dark():
    return (.10, .10, .10, 1.0)


def color_transmission_circle(args):
    if args.color_scheme == "light":
        return color_transmission_circle_light()
    else:
        return color_transmission_circle_dark()


def color_tx_links_light():
    return (.1, .1, .1, .4)


def color_tx_links_dark():
    return (.0, .0, .0, .4)


def color_tx_links(args):
    if args.color_scheme == "light":
        return color_tx_links_light()
    else:
        return color_tx_links_dark()


def draw_router_transmission(args, ld, area, r, img_idx):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, area.x, area.y)
    ctx = cairo.Context(surface)
    ctx.rectangle(0, 0, area.x, area.y)
    ctx.set_source_rgba(*color_db(args))
    ctx.fill()

    # transmitting circles
    for i in range(len(r)):
        router = r[i]
        x, y = router.coordinates()

        if router.transmission_within_second:
            ctx.set_source_rgba(*color_transmission_circle(args))
            ctx.move_to(x, y)
            ctx.arc(x, y, 50, 0, 2 * math.pi)
            ctx.fill()

    for i in range(len(r)):
        router = r[i]
        x, y = router.coordinates()

        ctx.set_line_width(0.1)
        path_thinkness = 6.0
        # iterate over links
        for i, t in enumerate(router.interfaces):
            range_ = t['range']
            interface_name = t['name']

            # draw lines between links
            ctx.set_line_width(path_thinkness)
            for r_id, r_obj in router.connections[interface_name].items():
                other_x, other_y = r_obj.coordinates()
                ctx.move_to(x, y)
                ctx.set_source_rgba(*color_tx_links(args))
                ctx.line_to(other_x, other_y)
                ctx.stroke()

            path_thinkness -= 4.0
            if path_thinkness < 2.0:
                path_thinkness = 2.0

    # draw dots over all
    for i in range(len(r)):
        router = r[i]
        x, y = router.coordinates()

        ctx.set_line_width(0.0)
        ctx.set_source_rgba(*color_tx_links(args))
        ctx.move_to(x, y)
        ctx.arc(x, y, 5, 0, 2 * math.pi)
        ctx.fill()

    full_path = os.path.join(ld, "images-tx", "{0:05}.png".format(img_idx))
    surface.write_to_png(full_path)


def image_merge(args, ld, img_idx):
    m_path = os.path.join(ld, "images-range-tx-merge",
                          "{0:05}.png".format(img_idx))
    r_path = os.path.join(ld, "images-range", "{0:05}.png".format(img_idx))
    t_path = os.path.join(ld, "images-tx", "{0:05}.png".format(img_idx))

    images = map(Image.open, [r_path, t_path])
    new_im = Image.new('RGB', (1920, 1080))

    x_offset = 0
    for image in images:
        new_im.paste(image, (x_offset, 0))
        x_offset += image.size[0]
    new_im.save(m_path, "PNG")


def draw_images(args, ld, area, r, img_idx):
    draw_router_loc(args, ld, area, r, img_idx)
    draw_router_transmission(args, ld, area, r, img_idx)

    image_merge(args, ld, img_idx)


def setup_img_folder(scenerio_name):
    for path in ("images-range", "images-tx", "images-range-tx-merge"):
        f_path = os.path.join("run-data", scenerio_name, path)
        if os.path.exists(f_path):
            shutil.rmtree(f_path)
        os.makedirs(f_path)


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
        draw_images(args, ld, area, r, sec)


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
        draw_images(args, ld, area, r, sec)


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
        draw_images(args, ld, area, r, sec)
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
            setup_img_folder(scenario[0])
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
