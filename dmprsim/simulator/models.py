import functools
import logging
import math
import random


class TimeWrapper(object):
    time = 0


def patch_log_record_factory():
    default_record_factory = logging.getLogRecordFactory()

    def patch_time_factory(*args, **kwargs):
        record = default_record_factory(*args, **kwargs)
        record.created = TimeWrapper.time
        return record

    logging.setLogRecordFactory(patch_time_factory)


patch_log_record_factory()


class MobilityArea(object):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.models = set()

    def start(self):
        for model in self.models:
            model.start()

    def step(self, time):
        TimeWrapper.time = time
        self._get_distance.cache_clear()
        for model in self.models:
            model.step()

    def get_neighbors(self, model, interface: dict) -> set:
        result = set()
        range_ = interface['range']
        for candidate in self.models:
            if candidate == model or not candidate.visible:
                continue
            if self._get_distance(frozenset((candidate, model))) <= range_:
                result.add(candidate.router)
        return result

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def _get_distance(models: frozenset) -> float:
        model1, model2 = tuple(models)
        return math.hypot(model1.x - model2.x, model1.y - model2.y)


class MobilityModel(object):
    def __init__(self, area: MobilityArea, coords: tuple = None,
                 disappearance_pattern: tuple = (0, 0, 0)):
        self.area = area
        area.models.add(self)
        if coords is None:
            self.x = random.randint(0, area.width)
            self.y = random.randint(0, area.height)
        else:
            self.x, self.y = coords

        self.disappearance_pattern = disappearance_pattern
        if random.random() < disappearance_pattern[0]:
            self.disappear = True
        else:
            self.disappear = False

        self.visible = True
        self.router = None

    def start(self):
        self.router.start()

    def step(self):
        self.toggle_visibility()
        self.router.step()

    def toggle_visibility(self):
        # call random.random() exactly once for every step so we stay
        # reproducible
        r = random.random()
        if self.disappear:
            if self.visible:
                self.visible = r > self.disappearance_pattern[1]
            else:
                self.visible = r < self.disappearance_pattern[2]

    def get_neighbors(self, interface: dict) -> set:
        if not self.visible:
            return set()
        return self.area.get_neighbors(self, interface)

    def coordinates(self):
        return self.x, self.y


class MovingMobilityModel(MobilityModel):
    def __init__(self, area: MobilityArea, coords: tuple = None,
                 disappearance_pattern: tuple = (0, 0, 0), velocity=lambda: 0):
        super(MovingMobilityModel, self).__init__(
            area=area, coords=coords,
            disappearance_pattern=disappearance_pattern
        )
        self.velocity = (velocity(), velocity())

    def step(self):
        v_x, v_y = self.velocity
        self.x += v_x
        self.y += v_y

        if int(self.x) not in range(self.area.width):
            v_x = -v_x
        if int(self.y) not in range(self.area.height):
            v_y = -v_y

        self.velocity = v_x, v_y

        super(MovingMobilityModel, self).step()
