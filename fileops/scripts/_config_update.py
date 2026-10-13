from pathlib import Path

import typer
from typing_extensions import Annotated


def update_cli(
        ini_path: Annotated[Path, typer.Argument(help="Path where config files are")],
        relative_to: Annotated[Path, typer.Option(help="Set to base where all paths should be relative to.")] = None,
):
    """
    Rename config folders to match the cfg_folder column of the Configs registry.
    """
    # imported locally to avoid a circular import (_config_map imports
    # rename_movie_filename from this module).
    from ._config_map import rename_config_folders

    content_path = Path(ini_path).parent / "cfg_content.xlsx"
    rename_config_folders(content_path, ini_path, relative_to=relative_to)


def rename_movie_filename(cfg_path: Path, old_fold: str, new_fold: str):
    """Rename the ``filename`` field of the MOVIE section(s) of a config file.

    The rendered movie files themselves are left untouched: only the config
    field that names them follows the renamed configuration folder. If the old
    folder name does not appear inside a MOVIE filename the field is left as
    it is (there is nothing to replace).
    """
    lines = cfg_path.read_text().splitlines(keepends=True)
    in_movie = False
    changed = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_movie = stripped[1:-1].strip().upper()[:5] == "MOVIE"
            continue
        if in_movie and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() == "filename" and old_fold in value:
                lines[i] = line.replace(old_fold, new_fold)
                changed = True
    if changed:
        cfg_path.write_text("".join(lines))