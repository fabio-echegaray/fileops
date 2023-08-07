import multiprocessing

import os
import stat
import subprocess
from pathlib import Path

from fileops.pathutils import ensure_dir


def _ld(from_path: Path, to_path: Path, file: str):
    if not os.path.exists(to_path / file):
        os.symlink(from_path / file, to_path / file)


def setup_sim_folder(cytosim_path: Path, sim_path: Path, number_of_runs=10):
    sim_path = ensure_dir(sim_path / "simulations")

    _ld(cytosim_path / "preconfig", sim_path, file="preconfig.py")
    _ld(cytosim_path / "preconfig", sim_path, file="collect.py")
    _ld(cytosim_path / "python" / "run", sim_path, file="go_sim.py")
    _ld(cytosim_path / "bin", sim_path, file="sim")

    # call preconfig to generate all simulations
    cwd = os.getcwd()
    os.chdir(sim_path)
    result = subprocess.run(["python", "preconfig.py", str(number_of_runs), "../template.cym.tpl"],
                            capture_output=True, text=True)
    with open("preconfig-output.txt", mode="w") as fd:
        fd.write(result.stderr)
        fd.writelines("\r\n--------------\r\n")
        fd.write(result.stdout)

    #  change permissions to generated files (remove executable flag otherwise it gets in conflict with cytosim scripts
    for file in os.listdir("."):
        if file.endswith(".cym"):
            os.chmod(file, stat.S_IREAD + stat.S_IWRITE)

    os.chdir(cwd)


def run_simulations(path: Path):
    """
    just run
    ls template*.cym | xargs -P 24 -L 1 python go_sim.py sim
    """
    # n_cores = multiprocessing.cpu_count()


if __name__ == "__main__":
    r = Path("/media/lab/Data/Fabio/Dev/")
    setup_sim_folder(
        cytosim_path=r / "Cpp-cytosim",
        sim_path=r / "Python-actomyosin-furrows/cytosim/aster_kinesin_actomyosin/transport_actin"
    )
