from dmprsim import Router
import os.path


def generate_routers(interfaces, mobility_models, log_directory):
    routers = []
    for i, model in enumerate(mobility_models):
        ld = os.path.join(log_directory, str(i))
        routers.append(Router(str(i), interfaces, model, ld))
    for router in routers:
        router.register_routers(routers)
        router.connect()
        router.start(0)
    return routers
