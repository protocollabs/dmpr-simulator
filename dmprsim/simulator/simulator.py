# -*- coding: utf-8 -*-

import ipaddress
import json
import logging
import math
import pathlib
import random

from core.dmpr import NoOpTracer, SimpleBandwidthPolicy, SimpleLossPolicy, dmpr
from core.dmpr.path import Path

DEFAULT_PACKET_TTL = 32

logger = logging.getLogger(__name__)


class ForwardException(Exception):
    pass


class TimeWrapper(object):
    time = 0

    @classmethod
    def step(cls):
        cls.time += 1


def patch_log_record_factory():
    default_record_factory = logging.getLogRecordFactory()

    def patch_time_factory(*args, **kwargs):
        record = default_record_factory(*args, **kwargs)
        record.created = TimeWrapper.time
        return record

    logging.setLogRecordFactory(patch_time_factory())


class JSONPathEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Path):
            return '>'.join(o.nodes)
        return json.JSONEncoder.default(self, o)


class Tracer(NoOpTracer):
    def __init__(self, directory: pathlib.Path, enable: list = None):
        self.enabled = {}
        if enable is not None:
            for tracer in enable:
                self.enable(tracer)

        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory

    def enable(self, tracepoint):
        if tracepoint not in self.enabled:
            path = self.directory / tracepoint
            self.enabled[tracepoint] = path.open('w')

    def get_files(self, tracepoint: str) -> list:
        result = []
        for i in self.enabled:
            if tracepoint.startswith(i):
                result.append(self.enabled[i])
        return result

    def log(self, tracepoint, msg, time):
        files = self.get_files(tracepoint)

        for file in files:
            json_msg = json.dumps(msg, sort_keys=True, cls=JSONPathEncoder,
                                  separators=(',', ':'))
            file.write('{} {}\n'.format(time, json_msg))


class Router:
    def __init__(self, id_, interfaces: list, mm, log_directory: pathlib.Path,
                 override_config={}, policies=None, tracer=None):
        self.id = id_

        tracer_dir = log_directory / 'trace'
        if tracer is None:
            tracer = Tracer
        self.tracer = tracer(tracer_dir)

        self.log = logger.getChild(str(self.id))

        self.log_directory = log_directory
        self.mm = mm
        self.interfaces = {iface['name']: iface for iface in interfaces}
        self.override_config = override_config

        self.routing_table = {}
        self.connections = {}
        self.interface_addr = {}
        self.is_transmitter = False
        self.is_receiver = False
        self.routers = []
        self.transmission_within_second = False
        self.forwarded_packets = list()

        self.gen_own_networks()

        self.policies = policies
        if policies is None:
            self.policies = (SimpleBandwidthPolicy(),
                             SimpleLossPolicy())

        for interface in interfaces:
            self.connections[interface['name']] = dict()
            self.interface_addr[interface['name']] = dict()
            self.interface_addr[interface['name']]['v4'] = self._rand_ip_addr(
                "v4")
            self.interface_addr[interface['name']]['v6'] = self._rand_ip_addr(
                "v6")

        self._setup_core()

    def _setup_core(self):
        self._core = dmpr.DMPR(tracer=self.tracer)

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
        for interface in self.interfaces.values():
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
        filename = self.log_directory / 'config'
        with filename.open('w') as file:
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
        self.log.debug("routing table update")
        self.routing_table = routing_table

    def _route_lookup(self, packet):
        tos = packet['tos']  # e.g. "lowest-loss"
        if not tos in self.routing_table:
            self.log.info("no policy routing table named: {}".format(tos))
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
            self.log.info(
                "packet reached destination with {} hops".format(hops))
            return

        packet['ttl'] -= 1
        packet['path'].append(self.id)

        try:
            router = self._route_lookup(packet)
        except ForwardException as e:
            self.log.info(
                "route lookup failed, drop packet, no next hop\n{}".format(e))
            self.log.info(packet['path'])
            return

        self.log.info("forward [{:10}] {:>4} -> {:>4}".format(packet['tos'],
                                                              self.id,
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
        self.log.debug(emsg.format(interface_name, proto, dst_mcast_addr))
        # send message to all connected routers
        for r_obj in self.connections[interface_name].values():
            r_obj.msg_rx(interface_name, msg_json)

    def msg_rx(self, interface_name, msg):
        if self.interfaces[interface_name].get('rx-loss', 0) > random.random():
            return
        msg_dict = json.loads(msg)
        self._core.msg_rx(interface_name, msg_dict)

    def register_routers(self, r):
        self.routers = r

    def get_time(self):
        return TimeWrapper.time

    def step(self, time):
        # new round, reset to no transmission
        self.transmission_within_second = False
        TimeWrapper.time = time
        self.mm.step()
        self.connect()
        self._core.tick()

    def start(self, time):
        TimeWrapper.time = time
        self._core.start()

    def stop(self):
        self._core.stop()

    def coordinates(self):
        return self.mm.coordinates()

    def connect_links(self, dist, other):
        for interface in self.interfaces.values():
            name = interface['name']
            range = interface['range']
            if dist <= range:
                self.connections[name][other.id] = other

    def connect(self):
        self.connections = {interface: {} for interface in self.interfaces}
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
        'dmprsim-router': src_id,
        'dst-prefix': dst_ip,
        'ttl': DEFAULT_PACKET_TTL,
        'tos': tos,
        'path': []
    }


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
