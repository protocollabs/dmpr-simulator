import random


class MiddlewareController(object):
    activated_middleware = list()

    @classmethod
    def activate(cls, middleware):
        assert isinstance(middleware, AbstractMiddleware)
        if middleware not in cls.activated_middleware:
            cls.activated_middleware.append(middleware)

    @classmethod
    def forward_routing_msg(cls, msg: dict, **kwargs) -> dict:
        for middleware in cls.activated_middleware:
            msg = middleware.forward_routing_msg(**kwargs, msg=msg)
        return msg

    @classmethod
    def forward_packet(cls, packet: dict, **kwargs) -> dict:
        for middleware in cls.activated_middleware:
            packet = middleware.forward_packet(**kwargs, packet=packet)
        return packet


class AbstractMiddleware(object):
    """
    A Middleware can be registered in the MiddlewareController and helps
    performing all tasks on a transmitted message or packet between a router and
    a destination
    """

    def forward_routing_msg(self, origin, destination,
                            interface_name: str, msg: dict) -> dict:
        """
        Get's called with all forwarded routing messages

        :param origin: The origin Router
        :param destination: The destination Router
        :param interface_name: The interface used on the Routers
        :param msg: The routing message
        :return: The routing message (may be modified) or None if forwarding
        should be stopped
        """
        return msg

    def forward_packet(self, origin, destination,
                       interface_name: str, packet: dict) -> dict:
        """
        Get's called with all forwarded packets (but not routing messages)

        These packets are used to simulate traffic in the network and can be
        modified by this middleware call

        :param origin: The origin Router
        :param destination: The destination Router
        :param interface_name: The interface used on the Routers
        :param packet: The forwarded packet
        :return: The forwarded packet (may be modified) or None if forwarding
        should be stopped
        """
        return packet


class RoutingMsgLossMiddleware(AbstractMiddleware):
    """
    Drops routing messages based on the loss property of the interface
    """

    def forward_routing_msg(self, origin, destination,
                            interface_name: str, msg: dict) -> dict:
        if origin.interfaces[interface_name].get('rx-loss',
                                                 0) > random.random():
            return None
        return msg


class RouterTransmittedMiddleware(AbstractMiddleware):
    """
    Logs routers which emitted a routing message for visualization
    """
    transmitting_routers = set()

    def forward_routing_msg(self, origin, destination,
                            interface_name: str, msg: dict) -> dict:
        if msg is None:
            return None
        self.transmitting_routers.add(origin)
        return msg

    @classmethod
    def reset(cls):
        cls.transmitting_routers = set()


class RouterForwardedPacketMiddleware(AbstractMiddleware):
    """
    Logs all transmitted packets for visualization
    """
    forwarded_packets = {}

    def forward_packet(self, origin, destination,
                       interface_name: str, packet: dict) -> dict:
        if packet is None:
            return None
        self.forwarded_packets.setdefault(origin, {})\
            .setdefault(destination,{})\
            .setdefault(interface_name, []).append(packet)
        return packet

    @classmethod
    def reset(cls):
        cls.forwarded_packets = {}

    @classmethod
    def has_transmitted(cls, router, neighbour, interface_name):
        return cls.forwarded_packets.get(router, {}).get(neighbour, {})\
            .get(interface_name, False)


class AsymmetricMiddleware(AbstractMiddleware):
    """
    Allows to register origin/destination pairs and drops routing messages from
    origin to destination with the configured probability
    """
    asymmetric_connections = {}

    def forward_routing_msg(self, origin, destination, interface_name: str,
                            msg: dict) -> dict:
        probability = self.asymmetric_connections.get((origin, destination), 0)
        if probability > random.random():
            return None
        return msg

    @classmethod
    def add(cls, origin, destination, probability):
        cls.asymmetric_connections[(origin, destination)] = probability
