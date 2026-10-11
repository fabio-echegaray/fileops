from typing import Optional


def build_config_map(cfg_root, relative_to=None, progress_callback=None):
    """Build the Configs registry DataFrame from the cfg files under cfg_root.

    One row per cfg file (multi-MOVIE files collapse to a single row); the
    columns are cfg_folder, cfg_path, image_path, image_series_id, has_movie.
    """
    raise NotImplementedError("Stage B")


def read_config_map(content_path):
    """Read the Configs sheet of a cfg_content workbook."""
    raise NotImplementedError("Stage B")


def write_config_map(content_path, df_map):
    """Replace only the Configs sheet, preserving the Content sheet."""
    raise NotImplementedError("Stage B")


def sync_config_map(content_path, cfg_root, summary_path=None, relative_to=None,
                    progress_callback=None):
    """Reconcile the Configs registry with the cfg files (and optionally the
    summary media rows), preserving user cfg_folder edits."""
    raise NotImplementedError("Stage B")


def rename_config_folders(content_path, cfg_root, relative_to=None,
                          progress_callback=None):
    """Rename cfg folders to match the Configs registry (git mv with -C,
    then rename the MOVIE filename field), updating cfg_path in the registry."""
    raise NotImplementedError("Stage B")