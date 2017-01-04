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

    def calc_file_path(self, id_):
        try:
            val = "{0:05}.log".format(int(id_))
        except ValueError:
            val = "{}.log".format(str(id_))
        return os.path.join(PATH_LOGS, val)


    def __init__(self, id_):
        file_path = self.calc_file_path(id_)
        self._log_fd = open(file_path, 'w')


    def msg(self, msg, time=str(datetime.datetime.now())):
        msg = "{} {}\n".format(time, msg)
        self._log_fd.write(msg)


    debug = msg
    info = msg
    warning = msg
    error = msg
    critical = msg



class Router:


    def __init__(self, id_, interfaces=None, mm=None):
        self.id = id_
        self.log = LoggerClone(id_)
        assert(mm)
        self.mm = mm
        assert(interfaces)
        self.interfaces=interfaces
        self.connections = dict()
        for interface in self.interfaces:
            self.connections[interface['name']] = dict()


    def register_router(self, r):
        self.r = r


    def step(self):
        self.mm.step()
        self.connect()


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



def rand_ip_prefix(type_):
    if type_ != "v4":
        raise Exception("Only v4 prefixes supported for now")
    addr = random.randint(0, 4000000000)
    a = socket.inet_ntoa(struct.pack("!I", addr))
    b = a.split(".")
    c = "{}.{}.{}.0/24".format(b[0], b[1], b[2])
    return c


def dist_update_all(r):
    for i in range(NO_ROUTER):
        for j in range(NO_ROUTER):
            if i == j: continue
            i_pos = r[i].pos()
            j_pos = r[j].pos()
            dist = math.hypot(i_pos[1] - j_pos[1], i_pos[0] - j_pos[0])
            r[j].dist_update(dist, r[i])


def draw_router_loc(area, r, path, img_idx):
    c_links = { 'tetra00' : (1.0, 0.15, 0.15, 1.0),  'wifi00' :(0.15, 1.0, 0.15, 1.0)}
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, area.x, area.y)
    ctx = cairo.Context(surface)
    ctx.rectangle(0, 0, area.x, area.y)
    ctx.set_source_rgba(0.15, 0.15, 0.15, 1.0)
    ctx.fill()

    for i in range(len(r)):
        router = r[i]
        x, y = router.coordinates()

        color = ((1.0, 1.0, 0.5, 0.05), (1.0, 0.0, 1.0, 0.05))
        ctx.set_line_width(0.1)
        path_thinkness = 4.0
        # iterate over links
        for i, t in enumerate(router.interfaces):
            range_ = t['range']
            ctx.set_source_rgba(*color[i])
            ctx.move_to(x, y)
            ctx.arc(x, y, range_, 0, 2 * math.pi)
            ctx.fill()

            # draw lines between links
            #ctx.set_line_width(path_thinkness)
            #for r_id, other in router.terminals[t['path_type']].connections.items():
            #    other_x, other_y = other.pos_x, other.pos_y
            #    ctx.move_to(x, y)
            #    ctx.set_source_rgba(*c_links[path_type])
            #    ctx.line_to(other_x, other_y)
            #    ctx.stroke()
            #path_thinkness -= 2.0

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

        # router IP prefix
        #ctx.set_font_size(8)
        #ctx.set_source_rgba(0.5, 1, 0.7, 0.5)
        #ctx.move_to(x + 10, y + 20)
        #ctx.show_text(router.prefix_v4)

    full_path = os.path.join(path, "{0:05}.png".format(img_idx))
    surface.write_to_png(full_path)


def draw_router_transmission(r, path, img_idx):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIMU_AREA_X, SIMU_AREA_Y)
    ctx = cairo.Context(surface)
    ctx.rectangle(0, 0, SIMU_AREA_X, SIMU_AREA_Y)
    ctx.set_source_rgba(0.15, 0.15, 0.15, 1.0)
    ctx.fill()

    # transmitting circles
    for i in range(NO_ROUTER):
        router = r[i]
        x = router.pos_x
        y = router.pos_y

        if router.transmitted_now:
            ctx.set_source_rgba(.10, .10, .10, 1.0)
            ctx.move_to(x, y)
            ctx.arc(x, y, 50, 0, 2 * math.pi)
            ctx.fill()

    for i in range(NO_ROUTER):
        router = r[i]
        x = router.pos_x
        y = router.pos_y

        color = ((1.0, 1.0, 0.5, 0.05), (1.0, 0.0, 1.0, 0.05))
        ctx.set_line_width(0.1)
        path_thinkness = 6.0
        # iterate over links
        for i, t in enumerate(router.ti):
            range_ = t['range']
            path_type = t['path_type']

            # draw lines between links
            ctx.set_line_width(path_thinkness)
            for r_id, other in router.terminals[t['path_type']].connections.items():
                other_x, other_y = other.pos_x, other.pos_y
                ctx.move_to(x, y)
                ctx.set_source_rgba(.0, .0, .0, .4)
                ctx.line_to(other_x, other_y)
                ctx.stroke()

            path_thinkness -= 4.0
            if path_thinkness < 2.0:
                path_thinkness = 2.0

    # draw dots over all
    for i in range(NO_ROUTER):
        router = r[i]
        x = router.pos_x
        y = router.pos_y

        ctx.set_line_width(0.0)
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(x, y)
        ctx.arc(x, y, 5, 0, 2 * math.pi)
        ctx.fill()

    full_path = os.path.join(path, "{0:05}.png".format(img_idx))
    surface.write_to_png(full_path)


def image_merge(merge_path, range_path, tx_path, img_idx):
    m_path = os.path.join(merge_path, "{0:05}.png".format(img_idx))
    r_path = os.path.join(range_path, "{0:05}.png".format(img_idx))
    t_path = os.path.join(tx_path,    "{0:05}.png".format(img_idx))

    images = map(Image.open, [r_path, t_path])
    new_im = Image.new('RGB', (1920, 1080))

    x_offset = 0
    for im in images:
        new_im.paste(im, (x_offset,0))
        x_offset += im.size[0]

    new_im.save(m_path, "PNG")


def draw_images(area, r, img_idx):
    draw_router_loc(area, r, PATH_IMAGES_RANGE, img_idx)
    #draw_router_transmission(r, PATH_IMAGES_TX, img_idx)

    #image_merge(PATH_IMAGES_MERGE, PATH_IMAGES_RANGE, PATH_IMAGES_TX, img_idx)


def setup_img_folder():
    for path in (PATH_IMAGES_RANGE, PATH_IMAGES_TX, PATH_IMAGES_MERGE):
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)


def gen_data_packet(src_id, dst_id, tos='low-loss'):
    packet = addict.Dict()
    packet.src_id = src_id
    packet.dst_id = dst_id
    packet.ttl = DEFAULT_PACKET_TTL
    packet.tos = tos
    return packet


def setup_log_folder():
    if os.path.exists(PATH_LOGS):
        shutil.rmtree(PATH_LOGS)
    os.makedirs(PATH_LOGS)


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
        # static
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



def two_router_basic():

    interfaces = [
        { "name" : "wifi0",  "range" : 210, "bandwidth" : 5000, "loss" : 5},
        { "name" : "tetra0", "range" : 250, "bandwidth" : 5000, "loss" : 10}
    ]

    area = MobilityArea(600, 500)
    r = []
    mm = StaticMobilityModel(area, 200, 250)
    r.append(Router("1", interfaces=interfaces, mm=mm))
    mm = StaticMobilityModel(area, 400, 250)
    r.append(Router("2", interfaces=interfaces, mm=mm))

    r[0].register_router(r)
    r[1].register_router(r)

    SIMU_TIME = 1000
    for sec in range(SIMU_TIME):
        sep = '=' * 50
        print("\n{}\nsimulation time:{:6}/{}\n".format(sep, sec, SIMU_TIME))
        for i in range(len(r)):
            r[i].step()
        draw_images(area, r, sec)


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
        [ "two-router-basis", two_router_basic ]
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
            setup_img_folder()
            setup_log_folder()
            scenario[1]()
            #cmd = "ffmpeg -framerate 10 -pattern_type glob -i 'images-merge/*.png' -c:v libx264 -pix_fmt yuv420p mdvrd.mp4"
            #print("now execute \"{}\" to generate a video".format(cmd))
            sys.exit(0)
    die()



if __name__ == '__main__':
    main()
