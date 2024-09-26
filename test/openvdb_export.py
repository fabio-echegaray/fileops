from pathlib import Path

from fileops.export._openvdb import export_paraview
from fileops.export.config import create_cfg_file, read_config

if __name__ == '__main__':
    base_exp_pth = Path("/Users/fabio/data/")
    base_cache_pth = Path("/Users/fabio/dev/Python-AgentSegmentation/out")
    exp_name = "20240924 - JupMCh MoeGFP/CHX_2"
    exp_file = f"CHX_2_MMStack_Pos0.ome.tif"
    img_path = base_exp_pth / exp_name / exp_file

    cfg_path = Path('../test_vol.cfg')
    if not cfg_path.exists():
        create_cfg_file(path=cfg_path,
                        contents={
                            "DATA": {
                                "image":   img_path.as_posix(),
                                "series":  0,
                                "channel": [0, 1],
                                "frame":   "all"
                            }
                        })
    cfg = read_config(cfg_path)

    save_path = Path("./out")
    save_path.mkdir(exist_ok=True)
    export_paraview(cfg, save_path)
