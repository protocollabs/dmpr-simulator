import cProfile
from pathlib import Path


def main(args, results_path: Path, scenario_path: Path):
    scenario_path.mkdir(parents=True, exist_ok=True)
    cProfile.runctx(
        'from dmprsim.scenarios.python_profile import main;'
        'main(args, scenario_path)',
        globals=globals(),
        locals=locals(),
        filename=str(results_path / 'profile'),
    )
