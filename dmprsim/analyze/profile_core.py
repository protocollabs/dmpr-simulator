import cProfile
from pathlib import Path


def main(args, results_dir: Path, scenario_dir: Path):
    try:
        scenario_dir.mkdir(parents=True)
    except FileExistsError:
        pass
    cProfile.runctx(
        'from dmprsim.scenarios.python_profile import main;'
        'main(args, results_dir, scenario_dir)',
        globals=globals(),
        locals=locals(),
        filename=str(results_dir / 'profile.pstats'),
    )
