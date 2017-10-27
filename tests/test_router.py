import contextlib
import copy
import tempfile

import pathlib
import pytest

from dmprsim.simulator.router import RouterDB, Router, ForwardException
from tests.mocks import MockRouter, MockModel, MockArea


class TestRouterDB(object):
    def _get_test_db(self):
        return copy.deepcopy(RouterDB)

    def test_adding(self):
        db = self._get_test_db()
        router = MockRouter()

        with pytest.raises(KeyError):
            db.by_addr('4')
        with pytest.raises(KeyError):
            db.by_addr('6')
        with pytest.raises(KeyError):
            db.by_prefix('prefix')
        with pytest.raises(KeyError):
            db.by_prefix('nonexistant')

        db.register_router(router)

        assert db.by_addr('4') is router
        assert db.by_addr('6') is router
        assert db.by_prefix('prefix') is router
        with pytest.raises(KeyError):
            db.by_prefix('nonexistant')

    def test_removing(self):
        db = self._get_test_db()
        router = MockRouter()

        db.register_router(router)
        assert db.by_addr('4') is router
        assert db.by_addr('6') is router
        assert db.by_prefix('prefix') is router
        with pytest.raises(KeyError):
            db.by_prefix('nonexistant')

        db.remove_router(router)
        with pytest.raises(KeyError):
            db.by_addr('4')
        with pytest.raises(KeyError):
            db.by_addr('6')
        with pytest.raises(KeyError):
            db.by_prefix('prefix')
        with pytest.raises(KeyError):
            db.by_prefix('nonexistant')


class TestRouter(object):
    @contextlib.contextmanager
    def _get_router(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = pathlib.Path(tmpdir)
            router = Router(id_='1', model=MockModel(), log_directory=tmpdir)
            yield router

    def test_get_random_network(self):
        with self._get_router() as router:
            network = router.get_random_network()
            assert network in router.networks

    def test_get_neighbors(self):
        with self._get_router() as router:
            assert router.get_connected_routers('wifi0') == {router}

    def test_route_lookup(self):
        with self._get_router() as router:
            network = router.get_random_network()
            addr = 'a1'
            list(router.interfaces.values())[0]['addr-v4'] = addr
            RouterDB.routers['by-addr'][addr] = router

            router.routing_table = {
                'tos': [
                    {'prefix': network, 'next-hop': addr, 'interface': 'wifi0'}
                ]
            }

            expected = router
            router, interface = router._route_lookup(
                {'tos': 'tos', 'dst-prefix': network}
            )
            assert router == expected
            assert interface == 'wifi0'

    def test_route_lookup_raises(self):
        with self._get_router() as router1:
            with self._get_router() as router2:
                router1.routing_table = {
                    'tos': [
                        {'prefix': 'p1', 'next-hop': 'a1',
                         'interface': 'wifi0'},
                        {'prefix': 'p2', 'next-hop': 'a2',
                         'interface': 'tetra0'},
                    ]
                }

                with pytest.raises(ForwardException,
                                   match='.*No routing table for tos.*'):
                    router1._route_lookup({'tos': 'nonexistant'})

                with pytest.raises(ForwardException,
                                   match='No routing table entry.*'):
                    router1._route_lookup({'tos': 'tos', 'dst-prefix': 'p3'})

                with pytest.raises(ForwardException,
                                   match="Fatal: Router for next-hop .* does not exist"):
                    router1._route_lookup({'tos': 'tos', 'dst-prefix': 'p2'})

                RouterDB.routers['by-addr']['a2'] = router2
                with pytest.raises(ForwardException,
                                   match="Router is not connected"):
                    router1._route_lookup({'tos': 'tos', 'dst-prefix': 'p2'})

    def test_forward_at_destination(self):
        with self._get_router() as router:
            network = router.get_random_network()
            packet = {'ttl': 10, 'dst-prefix': network}
            assert router._forward_packet(packet)

    def test_forward_ttl_timeout(self):
        with self._get_router() as router:
            packet = {'ttl': 0}
            assert not router._forward_packet(packet)

    def test_forward_no_route(self):
        with self._get_router() as router:
            packet = {'ttl': 10, 'tos': 'nonexistant', 'dst-prefix': 'prefix',
                      'path': []}
            assert not router._forward_packet(packet)

    def test_send_packet(self):
        with self._get_router() as router:
            assert not router.send_packet(destination='dest', tos='nonexistant')
