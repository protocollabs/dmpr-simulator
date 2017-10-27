class StartStepMixin(object):
    def __init__(self):
        self.started = False
        self.stepped = False

    def start(self):
        self.started = True

    def step(self):
        self.stepped = True


class MockModel(StartStepMixin):
    def __init__(self, area=None, x=0, y=0):
        StartStepMixin.__init__(self)
        if area is None:
            area = MockArea()
        area.models.add(self)
        self.x = x
        self.y = y
        self.visible = True
        self.router = None

    def get_neighbors(self, interface):
        return {self.router}


class MockRouter(StartStepMixin):
    def __init__(self, model=None):
        StartStepMixin.__init__(self)
        if model is None:
            model = MockModel()
        model.router = self
        self.networks = ['prefix']
        self.interfaces = {
            '1': {'addr-v4': '4', 'addr-v6': '6'}
        }

    def start(self):
        self.started = True


class MockArea(object):
    def __init__(self):
        self.width = self.height = 100
        self.models = set()
