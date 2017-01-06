#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time
import sys
import os
import json
import datetime
import argparse
import pprint
import socket
import struct
import functools
import uuid
import random
import math
import addict
import cairo
import shutil
import copy
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

random.seed(1)

# statitics variables follows
NEIGHBOR_INFO_ACTIVE = 0

PATH_LOGS = "logs"
PATH_IMAGES_RANGE = "images-range"
PATH_IMAGES_TX    = "images-tx"
PATH_IMAGES_MERGE = "images-merge"


class LoggerClone:

    def calc_file_path(self, directory, id_):
        try:
            val = "{0:05}.log".format(int(id_))
        except ValueError:
            val = "{}.log".format(str(id_))
        return os.path.join(directory, val)


    def __init__(self, directory, id_):
        file_path = self.calc_file_path(directory, id_)
        self._log_fd = open(file_path, 'w')


    def msg(self, msg, time=None):
        msg = "{} {}\n".format(time, msg)
        self._log_fd.write(msg)


    debug = msg
    info = msg
    warning = msg
    error = msg
    critical = msg



class Router:


    def __init__(self, id_, interfaces=None, mm=None, log_directory=None):
        self.id = id_
        self.log = LoggerClone(os.path.join(log_directory, "logs"), id_)
        self._log_directory = log_directory
        assert(mm)
        self.mm = mm
        assert(interfaces)
        self.interfaces=interfaces
        self.connections = dict()
        for interface in self.interfaces:
            self.connections[interface['name']] = dict()
        self.transmission_within_second = False

        self._setup_core()

    def _setup_core(self):
        self._core = core.dmpr.DMPR(log=self.log)

        self._core.register_routing_table_update_cb(self.routing_table_update_cb)
        self._core.register_msg_tx_cb(self.msg_tx_cb)
        self._core.register_get_time_cb(self.get_time)

        conf = self._gen_configuration()
        self._core.register_configuration(conf)


    def _generate_configuration(self):
        c = dict()
        c["id"] = self.id
        c["rtn-msg-interval"] = "30"
        c["rtn-msg-interval-jitter"] = "7"
        c["rtn-msg-hold-time"] = "90"

        c["mcast-v4-tx-addr"] = "224.0.1.1"
        c["mcast-v6-tx-addr"] = "ff05:0:0:0:0:0:0:2"
        c["proto-transport-enable"] = [ "v4"  ]

        c["interfaces"] = list()
        for interface in self.interfaces:
            entry = dict()
            entry["name"] = interface["name"]
            entry["addr-v4"] = self._rand_ip_addr("v4")
            entry["addr-v6"] = self._rand_ip_addr("v6")

            entry["link-characteristics"] = dict()
            characteristics = ("bandwidth", "loss")
            for characteristic in characteristics:
                if characteristic in interface:
                    entry["link-characteristics"][characteristic] = interface[characteristic]
            c["interfaces"].append(entry)

        c["networks"] = list()
        for i in range(2):
            entry = dict()
            entry["proto"] = "v4"
            prefix, prefix_len = self._rand_ip_prefix("v4")
            entry["prefix"] = prefix
            entry["prefix-len"] = prefix_len
            c["networks"].append(entry)

        return c


    def _dump_config(self, config):
        dir_ = os.path.join(self._log_directory, "configs")
        if not os.path.exists(dir_):
            os.makedirs(dir_)
        fn = os.path.join(dir_, self.id)
        with open(fn, 'w') as fd:
            fd.write("\n" * 2)
            fd.write(pprint.pformat(config))
            fd.write("\n" * 3)

    def _gen_configuration(self):
        conf = self._generate_configuration()
        self._dump_config(conf)
        return conf

    def routing_table_update_cb(self, routing_table):
        """ this function is called when core stated
        that the routing table should be updated
        """
        self.log.info("routing table update")

    def msg_tx_cb(self, interface_name, proto, dst_mcast_addr, msg):
        """ this function is called when core stated
        that a routing message must be transmitted
        """
        msg = "msg transmission [interface:{}, proto:{}, addr:{}]"
        self.log.info(msg.format(interface_name, proto, dst_mcast_addr), time=self._core._get_time())


    def register_router(self, r):
        self.r = r

    def get_time(self):
        return self._time

    def step(self, time):
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
            dist = math.hypot(own_cor[1] - other_cor[1], own_cor[0] - other_cor[0])
            self.connect_links(dist, neighbor)


    def _rand_ip_prefix(self, type_):
        if type_ == "v4":
            addr = random.randint(0, 4000000000)
            a = socket.inet_ntoa(struct.pack("!I", addr))
            b = a.split(".")
            c = "{}.{}.{}.0".format(b[0], b[1], b[2])
            return c, 24
        if type_ == "v6":
            addr = ':'.join('{:x}'.format(random.randint(0, 2**16 - 1)) for i in range(4))
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
            return ':'.join('{:x}'.format(random.randint(0, 2**16 - 1)) for i in range(8))
        raise Exception("only IPv4/IPv6 supported")

    def _id_generator(self):
        return str(uuid.uuid1())





def draw_router_loc(ld, area, r, img_idx):
    color_interface_links = ((1.0, 0.15, 0.15, 1.0), (0.15, 1.0, 0.15, 1.0),
                             (0.45, 0.2, 0.15, 1.0), (0.85, 0.5, 0.45, 1.0))
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, area.x, area.y)
    ctx = cairo.Context(surface)
    ctx.rectangle(0, 0, area.x, area.y)
    ctx.set_source_rgba(0.15, 0.15, 0.15, 1.0)
    ctx.fill()

    for i in range(len(r)):
        router = r[i]
        x, y = router.coordinates()

        color = ((1.0, 1.0, 0.5, 0.05), (1.0, 0.0, 1.0, 0.05),
                 (0.5, 1.0, 0.0, 0.05), (1.0, 0.5, 1.0, 0.05))
        ctx.set_line_width(0.1)
        path_thinkness = 5.0
        # iterate over links
        interfaces_idx = 0
        for i, t in enumerate(router.interfaces):
            range_ = t['range']
            interface_name = t['name']
            ctx.set_source_rgba(*color[i])
            ctx.move_to(x, y)
            ctx.arc(x, y, range_, 0, 2 * math.pi)
            ctx.fill()

            # draw lines between links
            ctx.set_line_width(path_thinkness)
            for r_id, r_obj in router.connections[interface_name].items():
                other_x, other_y = r_obj.coordinates()
                ctx.move_to(x, y)
                ctx.set_source_rgba(*color_interface_links[interfaces_idx])
                ctx.line_to(other_x, other_y)
                ctx.stroke()
            path_thinkness -= 1.0
            interfaces_idx += 1

    for i in range(len(r)):
        router = r[i]
        x, y = router.coordinates()

        # node middle point
        ctx.set_line_width(0.0)
        ctx.set_source_rgb(0.5, 1, 0.5)
        ctx.move_to(x, y)
        ctx.arc(x, y, 5, 0, 2 * math.pi)
        ctx.fill()

        # router id
        ctx.set_font_size(10)
        ctx.set_source_rgb(0.5, 1, 0.7)
        ctx.move_to(x + 10, y + 10)
        ctx.show_text(str(router.id))

    full_path = os.path.join(ld, "images-range" , "{0:05}.png".format(img_idx))
    surface.write_to_png(full_path)


def draw_router_transmission(ld, area, r, img_idx):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, area.x, area.y)
    ctx = cairo.Context(surface)
    ctx.rectangle(0, 0, area.x, area.y)
    ctx.set_source_rgba(0.15, 0.15, 0.15, 1.0)
    ctx.fill()

    # transmitting circles
    for i in range(len(r)):
        router = r[i]
        x, y = router.coordinates()

        if router.transmission_within_second:
            ctx.set_source_rgba(.10, .10, .10, 1.0)
            ctx.move_to(x, y)
            ctx.arc(x, y, 50, 0, 2 * math.pi)
            ctx.fill()

    for i in range(len(r)):
        router = r[i]
        x, y = router.coordinates()

        color = ((1.0, 1.0, 0.5, 0.05), (1.0, 0.0, 1.0, 0.05),
                (.0, 0.0, 0.5, 0.05), (1.0, 0.5, 1.0, 0.05))
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
                ctx.set_source_rgba(.0, .0, .0, .4)
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
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(x, y)
        ctx.arc(x, y, 5, 0, 2 * math.pi)
        ctx.fill()

    full_path = os.path.join(ld, "images-tx" , "{0:05}.png".format(img_idx))
    surface.write_to_png(full_path)


def image_merge(ld, img_idx):
    m_path = os.path.join(ld, "images-range-tx-merge", "{0:05}.png".format(img_idx))
    r_path = os.path.join(ld, "images-range", "{0:05}.png".format(img_idx))
    t_path = os.path.join(ld, "images-tx", "{0:05}.png".format(img_idx))

    images = map(Image.open, [r_path, t_path])
    new_im = Image.new('RGB', (1920, 1080))

    x_offset = 0
    for im in images:
        new_im.paste(im, (x_offset,0))
        x_offset += im.size[0]

    new_im.save(m_path, "PNG")


def draw_images(ld, area, r, img_idx):
    draw_router_loc(ld, area, r, img_idx)
    draw_router_transmission(ld, area, r, img_idx)

    image_merge(ld, img_idx)


def setup_img_folder(scenerio_name):
    for path in ("images-range", "images-tx", "images-range-tx-merge"):
        f_path = os.path.join("run-data", scenerio_name, path)
        if os.path.exists(f_path):
            shutil.rmtree(f_path)
        os.makedirs(f_path)


def gen_data_packet(src_id, dst_id, tos='low-loss'):
    packet = addict.Dict()
    packet.src_id = src_id
    packet.dst_id = dst_id
    packet.ttl = DEFAULT_PACKET_TTL
    packet.tos = tos
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
        assert(self.x >= 0 and self.x <= self.area.x)
        assert(self.y >= 0 and self.y <= self.area.y)

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



def two_router_static_in_range(scenario_name):
    ld = os.path.join("run-data", scenario_name)

    interfaces = [
        { "name" : "wifi0",  "range" : 210, "bandwidth" : 5000, "loss" : 5},
        { "name" : "tetra0", "range" : 250, "bandwidth" : 5000, "loss" : 10}
    ]

    area = MobilityArea(600, 500)
    r = []
    mm = StaticMobilityModel(area, 200, 250)
    r.append(Router("1", interfaces=interfaces, mm=mm, log_directory=ld))
    mm = StaticMobilityModel(area, 400, 250)
    r.append(Router("2", interfaces=interfaces, mm=mm, log_directory=ld))

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
        draw_images(ld, area, r, sec)


    #src_id = random.randint(0, NO_ROUTER - 1)
    #dst_id = random.randint(0, NO_ROUTER - 1)
    #packet_low_loss       = gen_data_packet(src_id, dst_id, tos='low-loss')
    #packet_high_througput = gen_data_packet(src_id, dst_id, tos='high-throughput')
    #for sec in range(SIMULATION_TIME_SEC):
    #    for i in range(NO_ROUTER):
    #        r[i].step()
    #    dist_update_all(r)
    #    draw_images(r, sec)
    #    # inject test data packet into network
    #    r[src_id].forward_data_packet(packet_low_loss)
    #    r[src_id].forward_data_packet(packet_high_througput)


scenarios = [
        [ "001-two-router-static-in-range", two_router_static_in_range ]
]

def die():
    print("scenario as argument required")
    for scenario in scenarios:
        print("  {}".format(scenario[0]))
    sys.exit(1)

def main():
    if len(sys.argv) > 1:
        scenario_name = sys.argv[1]
    else:
        die()

    for scenario in scenarios:
        if scenario_name == scenario[0]:
            setup_img_folder(scenario[0])
            setup_log_folder(scenario[0])
            scenario[1](scenario[0])
            #cmd = "ffmpeg -framerate 10 -pattern_type glob -i 'images-merge/*.png' -c:v libx264 -pix_fmt yuv420p mdvrd.mp4"
            #print("now execute \"{}\" to generate a video".format(cmd))
            sys.exit(0)
    die()



if __name__ == '__main__':
    main()
