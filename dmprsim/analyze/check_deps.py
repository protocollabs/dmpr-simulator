import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def main(args, result_path: Path, scenario_path: Path) -> bool:
    error = False
    for module in ('PIL', 'seqdiag', 'matplotlib', 'numpy', 'pandas'):
        try:
            importlib.import_module(module)
        except ImportError:
            logger.warning("Cannot find {}".format(module))
            error = True

    try:
        import cairo
    except ImportError:
        try:
            import cairocffi
        except ImportError:
            logger.warning('Cannot find cairo or cairocffi')
            error = True

    if error:
        return error
    try:
        from .disappearing_node import main
        main(args, result_path, scenario_path)
    except Exception:
        logger.exception('Failed to run scenario')

    return error
