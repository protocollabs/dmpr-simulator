from dmprsim.simulator.models import TimeWrapper, MobilityArea, \
    MovingMobilityModel, MobilityModel

from tests.mocks import MockRouter, MockModel, MockArea


def test_timewrapper():
    TimeWrapper.time = 0
    assert TimeWrapper.time == 0
    TimeWrapper.time = 1
    assert TimeWrapper.time == 1


class TestMobilityArea(object):
    def _get_area(self):
        area = MobilityArea(100, 100)
        for i in range(2):
            MockModel(area, 50, i * 50)
        return area

    def test_start(self):
        area = self._get_area()
        assert not all(m.started for m in area.models)
        area.start()
        assert all(m.started for m in area.models)

    def test_step(self):
        area = self._get_area()
        TimeWrapper.time = 0
        assert not all(m.stepped for m in area.models)
        area.step(1)
        assert TimeWrapper.time == 1
        assert all(m.stepped for m in area.models)

    def test_get_distance(self):
        area = self._get_area()
        models = frozenset(area.models)
        assert area._get_distance(models) == 50

    def test_get_neighbors(self):
        area = self._get_area()
        m1, m2 = tuple(area.models)
        assert m1 is not m2

        m1.router = object()
        m2.router = object()

        expected = {m2.router}
        interface_too_short = {'range': 30}
        interface_long_enough = {'range': 60}
        interface_exact = {'range': 50}
        assert area.get_neighbors(m1, interface_too_short) == set()
        assert area.get_neighbors(m1, interface_long_enough) == expected
        assert area.get_neighbors(m1, interface_exact) == expected


class TestMobilityModel(object):
    def _get_model(self):
        model = MobilityModel(MockArea())
        MockRouter(model)
        return model

    def test_start(self):
        model = self._get_model()
        assert not model.router.started
        model.start()
        assert model.router.started

    def test_step(self):
        model = self._get_model()
        assert not model.router.stepped
        model.step()
        assert model.router.stepped

    def test_toggle_visibility(self):
        model = self._get_model()
        model.disappear = True
        model.disappearance_pattern = (0, 1, 1)
        assert model.visible
        model.step()
        assert not model.visible
        model.step()
        assert model.visible

    def test_coordinates(self):
        model = self._get_model()
        assert (model.x, model.y) == model.coordinates()


class TestMovingMobilityModel(object):
    def _get_model(self, velocity):
        model = MovingMobilityModel(MockArea(), coords=(0, 0),
                                    velocity=velocity)
        MockRouter(model)
        return model

    def test_step_zero_velocity(self):
        model = self._get_model(lambda: 0)
        assert not model.router.stepped
        assert model.coordinates() == (0, 0)

        model.step()
        assert model.router.stepped
        assert model.coordinates() == (0, 0)

    def test_step_nonzero_velocity(self):
        model = self._get_model(lambda: 1)
        assert not model.router.stepped
        assert model.coordinates() == (0, 0)

        model.step()
        assert model.router.stepped
        assert model.coordinates() == (1, 1)
