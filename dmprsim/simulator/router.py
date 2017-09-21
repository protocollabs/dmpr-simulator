# -*- coding: utf-8 -*-
import copy
import ipaddress
import json
import logging
import pathlib
import random

from core.dmpr import NoOpTracer, SimpleBandwidthPolicy, SimpleLossPolicy, DMPR
from core.dmpr.path import Path
from .models import TimeWrapper
from .middlewares import MiddlewareController

DEFAULT_PACKET_TTL = 32

DEFAULT_INTERFACES = [
    {
        "name": "wifi0",
        "range": 50,
        "simulate-loss": 10,
        "core-config": {
            "link-attributes": {"bandwidth": 8000, "loss": 10},
            "asymm-detection": False,
        }
    },
    {
        "name": "tetra0",
        "range": 100,
        "simulate-loss": 5,
        "core-config": {
            "link-attributes": {"bandwidth": 1000, "loss": 5},
            "asymm-detection": False,
        }
    },
]

logger = logging.getLogger(__name__)


class ForwardException(Exception):
    pass


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


class RouterDB(object):
    """
    A global router database for indexing routers by prefix and address.
    """
    routers = {
        'by-addr': {},
        'by-prefix': {},
    }

    @classmethod
    def register_router(cls, router: 'Router'):
        for network in router.networks:
            cls.routers['by-prefix'][network] = router
        for interface in router.interfaces.values():
            cls.routers['by-addr'][interface['addr-v4']] = router
            cls.routers['by-addr'][interface['addr-v6']] = router

    @classmethod
    def remove_router(cls, router: 'Router'):
        for network in router.networks:
            del cls.routers['by-prefix'][network]
        for interface in router.interfaces.values():
            del cls.routers['by-addr'][interface['addr-v4']]
            del cls.routers['by-addr'][interface['addr-v6']]

    @classmethod
    def by_addr(cls, addr: str) -> 'Router':
        return cls.routers['by-addr'][addr]

    @classmethod
    def by_prefix(cls, prefix: str) -> 'Router':
        return cls.routers['by-prefix'][prefix]


class Router(object):
    def __init__(self, id_, model, log_directory: pathlib.Path,
                 interfaces: list = DEFAULT_INTERFACES, config_override={},
                 policies=None, tracer_cls=None):
        self.id = id_
        self.log_directory = log_directory
        self.config_override = config_override

        self.model = model
        model.router = self

        tracer_dir = log_directory / 'trace'
        if tracer_cls is None:
            tracer_cls = Tracer
        self.tracer = tracer_cls(tracer_dir)

        self.log = logger.getChild(str(id_))

        if policies is None:
            policies = (
                SimpleBandwidthPolicy(),
                SimpleLossPolicy(),
            )

        self.routing_table = {}
        self.is_receiver = False
        self.is_transmitter = False

        self.networks, self.interfaces, config = self._get_configuration(
            interfaces)
        self._save_configuration(config)

        self.core = DMPR(tracer=self.tracer)

        self.core.register_routing_table_update_cb(self.routing_table_update_cb)
        self.core.register_msg_tx_cb(self.msg_tx_cb)
        self.core.register_get_time_cb(self.get_time)
        self.core.register_configuration(config)
        for policy in policies:
            self.core.register_policy(policy)

    def _get_configuration(self, conf_interfaces: list):
        networks = set()
        router_interfaces = {}
        config = {
            "id": self.id,
            "mcast-v4-tx-addr": "224.0.1.1",
            "mcast-v6-tx-addr": "ff05:0:0:0:0:0:0:2",
            "interfaces": list(),
            "networks": list(),
        }

        for interface in conf_interfaces:
            core_interface = copy.deepcopy(interface['core-config'])
            core_interface['name'] = interface['name']

            router_interface = copy.deepcopy(interface)

            addr = {
                'addr-v4': self._rand_ip_addr(version=4),
                'addr-v6': self._rand_ip_addr(version=6),
            }
            core_interface.update(addr)
            router_interface.update(addr)

            config['interfaces'].append(core_interface)
            router_interfaces[interface['name']] = router_interface

        for version in (4, 6):
            prefix, prefix_len = self._rand_ip_prefix(version)
            networks.add(prefix)
            entry = {
                "proto": "v{}".format(version),
                "prefix": prefix,
                "prefix-len": prefix_len,
            }
            config["networks"].append(entry)

        config.update(self.config_override)

        return networks, router_interfaces, config

    def _save_configuration(self, config):
        filename = self.log_directory / 'config'
        with filename.open('w') as file:
            file.write(json.dumps(config, sort_keys=True,
                                  indent=4, separators=(',', ': ')))

    # Runtime methods

    def step(self):
        self.core.tick()

    def start(self):
        RouterDB.register_router(self)
        self.core.start()

    def stop(self):
        self.core.stop()
        RouterDB.remove_router(self)

    # Callbacks

    def routing_table_update_cb(self, routing_table):
        self.log.debug("New Routing Table")
        self.routing_table = routing_table

    def msg_tx_cb(self, interface_name: str, proto: str, dst_mcast_addr: str,
                  msg: str):
        msg_json = json.dumps(msg)
        self.log.debug(
            "msg transmission {}, {}, {}".format(interface_name, proto,
                                                 dst_mcast_addr))
        msg_dict = json.loads(msg_json)
        for router in self.get_connected_routers(interface_name):
            msg = MiddlewareController.forward_routing_msg(
                origin=self,
                destination=router,
                interface_name=interface_name,
                msg=msg_dict
            )
            if msg is None:
                continue
            router.msg_rx(interface_name, msg)

    @staticmethod
    def get_time():
        return TimeWrapper.time

    # Routing Messages

    def msg_rx(self, interface_name: str, msg: dict):
        self.core.msg_rx(interface_name, msg)

    # Packet Forwarding

    def send_packet(self, destination: str, tos: str):
        """
        Forward mock traffic to test connectivity and routes in the network

        :param destination: The destination prefix
        :param tos: The policy to use while forwarding
        :return: bool, true if forwarding succeeded
        """
        packet = {
            'dst-prefix': destination,
            'ttl': DEFAULT_PACKET_TTL,
            'tos': tos,
        }
        return self._forward_packet(packet)

    def _route_lookup(self, packet: dict):
        if packet['tos'] not in self.routing_table:
            raise ForwardException(
                "No routing table for tos {}".format(packet['tos']))

        tos_table = self.routing_table[packet['tos']]
        dst_prefix = packet['dst-prefix']
        # Get the routing table entry for the packet tos and destination, there
        # should be only one, False when none is found
        route_entry = next((e for e in tos_table if e['prefix'] == dst_prefix),
                           False)
        if not route_entry:
            raise ForwardException(
                "No routing table entry for destination {}".format(dst_prefix))

        try:
            dest_router = RouterDB.by_addr(route_entry['next-hop'])
        except KeyError:
            raise ForwardException(
                "Fatal: Router for next-hop {} does not exist".format(
                    route_entry['next-hop']))

        if dest_router not in self.get_connected_routers(
                route_entry['interface']):
            raise ForwardException("Destination Router is not connected")

        return dest_router, route_entry['interface']

    def _forward_packet(self, packet: dict):
        if packet['ttl'] <= 0:
            self.log.info('drop packet, ttl 0')
            return False

        if packet['dst-prefix'] in self.networks:
            hops = DEFAULT_PACKET_TTL - packet['ttl']
            self.log.info("packet reached destination in {} hops".format(hops))
            return True

        packet['ttl'] -= 1

        try:
            dest_router, interface_name = self._route_lookup(packet)
        except ForwardException as e:
            self.log.info(e)
            return False

        self.log.info("forward [{:10}] {:>4} -> {:>4}".format(packet['tos'],
                                                              self.id,
                                                              dest_router.id))

        packet = MiddlewareController.forward_packet(
            origin=self,
            destination=dest_router,
            interface_name=interface_name,
            packet=packet,
        )
        if packet is None:
            return False

        return dest_router._forward_packet(packet)

    def get_connected_routers(self, interface_name):
        return self.model.get_neighbors(self.interfaces[interface_name])

    # Helpers

    def get_random_network(self):
        return random.choice(tuple(self.networks))

    @classmethod
    def _rand_ip_prefix(cls, version):
        """Return a random IPv<version> /24 or /72 network."""
        addr = cls._rand_ip_addr(version)
        prefix_len = (version - 3) * 24
        network = ipaddress.ip_network('{}/{}'.format(addr, prefix_len),
                                       strict=False)
        return str(network.network_address), prefix_len

    @classmethod
    def _rand_ip_addr(cls, version: int):
        """Return a random IPv<version> address"""
        assert version in (4, 6)
        return str(ipaddress.ip_address(
            random.randint((version - 4) ** 32, 2 ** (32 * (version - 3)) - 1)))
