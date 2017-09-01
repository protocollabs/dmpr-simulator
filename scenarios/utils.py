from dmprsim import Router


def generate_routers(interfaces, mobility_models, log_directory):
    routers = []
    for i, model in enumerate(mobility_models):
        routers.append(Router(str(i), interfaces, model, log_directory))
    for router in routers:
        router.register_routers(routers)
        router.connect()
        router.start(0)
    return routers
