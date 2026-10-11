# Configuration-location registry — design decisions

Status: planned (not yet implemented)
Date: 2026-10-11
Related: FileOps TODO #56, #57; ExperimentTrackerGUI TODO #33 (closes #13)

This document records the design decisions for decoupling the
configuration-folder relationship from the media summary and standardising
the spreadsheet artefacts on a single, versioned xlsx format. It is the
reference for the implementation and must be kept in sync with it.

## 1. Problem

The *desired* configuration folder name lives in the media summary's
`cfg_folder` column (`fileops/scripts/summary.py`, created in `make()`;
consumed as the rename target by `fileops/scripts/_config_update.py`).
The rename driver is therefore stored inside a media artefact:

- When new media is added the summary becomes obsolete or is absent, so
  there is no `cfg_folder` value to drive a rename even though the cfg
  files still exist.
- `read_cfg_associations()` / `restore_cfg_associations()`
  (`fileops/scripts/summary.py`) exist only to smuggle `cfg_path` /
  `cfg_folder` through summary regeneration — a workaround for that
  coupling.
- The GUI's update action (`src/gui/main.py`) requires both a summary and
  cfg files, so it cannot rename config folders from cfg files alone.

The goal is to be able to rename configuration folders and files when the
media summary is missing or stale, and when the media files themselves are
missing or only partially present.

A second problem is format redundancy: `make()` writes both a CSV
(`summary.csv`) and an xlsx (`summary.csv.xlsx`), and `read_summary_list()`
accepts `.xls/.xlsx`, `.ods/.fods` and `.csv`. Only OOXML xlsx can carry a
workbook-level metadata marker, so the extra formats cannot participate in a
single schema rule.

## 2. Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Where the registry lives | New `Configs` sheet inside `cfg_content.xlsx` |
| 2 | Scope | Full decoupling: remove `cfg_path`/`cfg_folder` from the summary |
| 3 | Sequencing | Write the contract tests first (avoid regressions) |
| 4 | Rename driver | Edit `cfg_folder` in place in the registry |
| 5 | Rename targets | The cfg folder and the MOVIE `filename` field only (rendered media untouched) |
| 6 | Generation input | Desired folders come from the registry; media metadata is looked up live from the summary |
| 7 | Schema/version marker | Workbook document properties (`wb.properties`) |
| 8 | Legacy files | Detect and hard-fail (`LegacyFormatError`), no in-place migration |
| 9 | Canonical format | xlsx only: `summary.xlsx` and `cfg_content.xlsx`; drop CSV/ODS I/O and the duplicate CSV write |
| 10 | `fileops-summary merge` | Also move to xlsx in/out |

Rationale highlights:

- **A registry sheet, not a separate file** keeps all cfg metadata in one
  place and reuses the existing, already-independent `cfg_content.xlsx`
  (which is generated from cfg files alone and therefore survives summary
  loss). The registry is per cfg file (one row each), which also removes
  the multi-MOVIE ambiguity that a per-MOVIE sheet would have.
- **Document properties** avoid adding a sheet (no sheet-order issues with
  `edit_config_content`, which reads the content sheet) and are a standard
  OOXML feature. A within-xlsx structural fallback covers properties that
  may be stripped by an external save.
- **Hard-fail legacy** keeps the schema rule simple and unambiguous. Old
  files are regenerated (summary from media, `cfg_content.xlsx` from the
  cfg folder) rather than converted in place.
- **xlsx only** makes the schema rule hold for every artefact and removes a
  whole class of edge cases.

## 3. Target data model

`cfg_content.xlsx`:

- `Content` (sheet name for the existing sheet 0): one row per MOVIE header,
  the output of `build_config_list()`. Used by `edit_config_content()`.
- `Configs` (new): one row per image series that either has a cfg file or is
  a candidate for one.

  | column | meaning |
  |--------|---------|
  | `cfg_folder` | desired folder name; edited in place -> rename driver |
  | `cfg_path` | current cfg path; empty = no cfg yet |
  | `image_path` | resolved image path (from the cfg, or the summary) |
  | `image_series_id` | image series id |
  | `has_movie` | whether the cfg defines a MOVIE section |

`summary.xlsx`:

- `Channels`, `Files-Timeseries`, `Files-Stills` — media only.
- No `cfg_path` / `cfg_folder` columns.

## 4. Schema & versioning

New `fileops/scripts/_schema.py`, mirroring the `MD_CACHE_SCHEMA` convention
in `fileops/image/_cache_metadata.py`:

- `SCHEMA_SUMMARY = "fileops-summary"`
- `SCHEMA_CFG_CONTENT = "fileops-cfg-content"`
- `SUMMARY_SCHEMA_VERSION = 2`
- `CFG_CONTENT_SCHEMA_VERSION = 2`
- `set_workbook_schema(book, kind, version)`: writes a compact JSON into
  `book.properties.description`, e.g.
  `{"schema": "fileops-summary", "schema_version": 2, "app_version": "0.4.0"}`,
  and sets `title`/`subject` for humans.
- `read_workbook_schema(path) -> (kind, version) | None`: reads workbook
  properties with `openpyxl.load_workbook(read_only=True)` (pandas
  `read_excel` does not expose them).
- `detect_summary_schema(path)` / `detect_cfg_content_schema(path)`:

  1. Use document properties when present.
  2. Otherwise fall back to structure within the xlsx (legacy summary: has
     `cfg_path`/`cfg_folder`; legacy cfg content: no `Configs` sheet).
  3. Anything else raises `LegacyFormatError` (hard-fail) with a message
     telling the user to regenerate the file.

Writers stamp the marker: `make()` sets properties on `writer.book`;
`generate_config_content()` and the registry writers stamp
`cfg_content.xlsx` (append mode sets properties on the loaded book).

## 5. Functions / API (FileOps)

New `fileops/scripts/_config_map.py`, exported from
`fileops/scripts/__init__.py`:

- `build_config_map(cfg_root, relative_to=None, progress_callback=None) -> DataFrame`
  one row per cfg file, from `build_config_list()` deduplicated on
  `cfg_path`.
- `read_config_map(content_path) -> DataFrame`
- `write_config_map(content_path, df_map)`: replaces only the `Configs`
  sheet, preserving `Content` and the latex table.
- `sync_config_map(content_path, cfg_root, summary_path=None, relative_to=None, ...)`:
  registry = cfg files (union) summary media rows, preserving existing
  user `cfg_folder` edits and `cfg_path` values.
- `rename_config_folders(content_path, cfg_root, relative_to=None, ...)`:
  read `Configs`; per cfg run `git -C <old.parent> mv` (keeping the
  `-C` fix) followed by `rename_movie_filename`; update `cfg_path` in the
  registry; ambiguity guard on `(image_path, image_series_id)`.

Reworked:

- `_config_edit.generate_config_content()` writes both `Content` and
  `Configs` sheets and stamps the schema marker.
- `_config_generate.generate()` reads the desired `cfg_folder` from
  `Configs` and looks up `channel_names` / folder live from the summary by
  `(image_path, image_series_id)`.
- `_config_update.update()` is replaced by `rename_config_folders()`.
- `summary.update_from_cfg_folder()` becomes `sync_config_map()`;
  `read_cfg_associations()` / `restore_cfg_associations()` are removed;
  `make_summary_and_sync()` is trimmed accordingly; `make()` and
  `__columns_reordered__` drop the cfg columns.
- `_utils.read_summary_list()` reads xlsx only (the `pandas_ods_reader`
  import and the CSV branch are removed) and enforces the schema.
- `summary.make()` / `make_summary_and_sync()` / CLI: a single
  `summary.xlsx`; `merge()` reads and writes xlsx.

## 6. Flows

- **Registry sync**: `sync_config_map()` seeds/refreshes `Configs` from the
  cfg files, optionally enriched with summary media rows; existing edits
  are preserved, new cfg rows get the current folder name.
- **Rename** (summary-independent): edit `cfg_folder` in `Configs`, run
  `rename_config_folders()`. Works with no summary and with missing media.
- **Coverage**: registry rows with an empty `cfg_path` have no cfg yet.
- **Generation**: rows in `Configs` with a `cfg_folder` but no `cfg_path`
  get a cfg created, with media metadata resolved live from the summary.

## 7. Implementation stages

### Stage A — contract tests first (red)

- `test/test_schema.py`: document-properties round-trip; detect new;
  detect stripped properties via structure; legacy -> `LegacyFormatError`.
- `test/test_config_map.py`: `build_config_map` (one row per cfg,
  multi-MOVIE collapse, panel-only, absolute/relative paths); `Configs`
  round-trip; user edit preserved; rename with no summary; rename with the
  media file missing; two cfg files in one folder.
- Retarget the rename tests in `test/test_update_from_cfg_folder.py`
  (`test_renaming_cfg_folder_moves_nested_config_and_updates_moviefile`,
  `test_renaming_config_folders_with_relative_to_matches_and_moves`,
  `test_git_rename_shows_as_rename_with_caller_in_other_repo`) and the
  `relative_to` cases to drive the registry; re-express the summary-merge
  tests against the registry.
- Delete `test/test_cfg_associations.py`.
- `test_read_summary_list.py` / `test_summary_cli.py` / `test_config_cli.py`:
  drop CSV/ODS cases, use `summary.xlsx`.
- GUI `tests/test_path_utils_config.py`: summary-less update; both-sheet
  generation.

### Stage B — FileOps

Implement section 5 above, including `_schema.py` and the hard-fail.

### Stage C — GUI

- `src/path_utils/_config.py`: `update_summary_and_configs()` -> registry
  sync + `rename_config_folders()`; allow the update with cfgs +
  `cfg_content.xlsx` and no summary; add a cfg-folder -> `cfg_content.xlsx`
  path.
- `src/gui/main.py`: canonical `summary.xlsx` (default `summary_path` and
  `_checkForFilesInit()` stem `summary`); state machine
  (`updateSummaryOrConfig` et al.); remove the summary/content
  cross-disable (GUI TODO #13); read the common cfg path from the
  `Configs` sheet; surface `LegacyFormatError` in `lbl_update_status`.

### Stage D — docs & TODO

- Update `docs/main.md` (Modes 2-4) and the GUI
  `design/functionality_report.md`.
- FileOps TODO #56, #57; GUI TODO #33.

### Stage E — verification

- FileOps full `test/` suite; GUI `tests/`.

## 8. Legacy handling / migration

- Legacy (v1) files are detected and rejected with `LegacyFormatError`.
- There is no in-place migration. Users regenerate the summary from the
  media and `cfg_content.xlsx` from the cfg folder.
- An opt-in `migrate` command could be added later if needed; it is
  explicitly out of scope here.

## 9. Impacted files

FileOps:

- `fileops/scripts/_config_map.py` (new)
- `fileops/scripts/_schema.py` (new)
- `fileops/scripts/_config_edit.py`
- `fileops/scripts/_config_generate.py`
- `fileops/scripts/_config_update.py`
- `fileops/scripts/summary.py`
- `fileops/scripts/_utils.py`
- `fileops/scripts/__init__.py`
- `fileops/scripts/config.py`
- `test/` (see Stage A)
- `TODO.txt`

ExperimentTrackerGUI:

- `src/path_utils/_config.py`
- `src/gui/main.py`
- `tests/test_path_utils_config.py`
- `docs/main.md`
- `design/functionality_report.md`
- `TODO.txt`

## 10. Risks

- `test/test_update_from_cfg_folder.py` is large and will be substantially
  retargeted; the contract tests in Stage A pin the behaviour before the
  refactor.
- Document properties can be stripped by some save paths; the structural
  fallback covers this for the current formats.
- Hard-failing legacy files means existing artefacts must be regenerated;
  this is intended and documented.
