import ast
import os
import sys

import pandas as pd
import numpy as np
import shapely.wkt
from pandas import StringDtype
from shapely.geometry.base import BaseGeometry

from fileops.pathutils import ensure_dir


def shapely_to_text(df):
    for col in df.columns:
        if issubclass(type(df[col].dropna().iloc[0]), BaseGeometry):
            df.loc[:, col] = df[col].apply(lambda r: shapely.wkt.dumps(r))
    return df


def text_to_shapely(df):
    # print(df.info())
    for col in df.columns:
        if df[col].dtype == object or df[col].dtype == StringDtype:
            # take first non-nan sample and check whether is a wkt primitive
            geom_wkt = df[col].dropna().iloc[0].split(' ')[0].split('(')[0]
            if geom_wkt == 'POINT' or \
                    geom_wkt == 'MULTIPOINT' or \
                    geom_wkt == 'LINESTRING' or \
                    geom_wkt == 'MULTILINESTRING' or \
                    geom_wkt == 'POLYGON' or \
                    geom_wkt == 'MULTIPOLYGON' or \
                    geom_wkt == 'TRIANGLE' or \
                    geom_wkt == 'POLYHEDRALSURFACE' or \
                    geom_wkt == 'TIN' or \
                    geom_wkt == 'GEOMETRYCOLLECTION':
                df.loc[:, col] = df[col].apply(lambda r: shapely.wkt.loads(r))
    return df


def numpy_to_text(df):
    for col in df.columns:
        if issubclass(type(df[col].dropna().iloc[0]), np.ndarray):
            df.loc[:, col] = df[col].apply(
                lambda r: f'NumPyNdarray{r.shape}' + np.array2string(r.ravel(), threshold=sys.maxsize)
            )
    return df


def text_to_ndarray(df):
    for col in df.columns:
        if df[col].dtype == object or df[col].dtype == StringDtype:
            # take first non-nan sample and check whether is a wkt primitive
            np_txt = df[col].dropna().iloc[0][0:12]
            if np_txt == 'NumPyNdarray':
                df.loc[:, col] = df[col].apply(lambda r:
                                               np.fromstring(r.split(')')[1])
                                               .reshape(ast.literal_eval(
                                                   r.split('(')[1].split(')')[0])
                                               ))
    return df


class SaveMixin:
    """
    A Mixin intended to save computed dataframes on disk.
    """
    log = None

    def __init__(self, df_dict: dict = None, folder="_sav", **kwargs):
        if df_dict is None or (type(df_dict) == dict and not df_dict):
            raise AttributeError("No dataframe definition.")
        for prop in df_dict.keys():
            # assert type(getattr(self, prop)) == pd.DataFrame, "Only Pandas DataFrames implemented in this Mixin."
            if not hasattr(self, prop):
                raise AttributeError(f"All properties must be included in class. Missing property {prop}.")

        self._save_properties = {k: v[:-4] if v[-4:] == '.csv' else v for (k, v) in df_dict.items()}
        self._save_folder = ensure_dir(folder)
        self._load()
        super().__init__(**kwargs)

    def __del__(self):
        self._save()

    def _save(self):
        self.log.info(f"Saving dataframe attributes to {self._save_folder}.")
        for key, value in self._save_properties.items():
            self.log.debug(f"Saving {key} into {value}.csv.")
            df = (getattr(self, key, default=[]).copy()
                  .pipe(numpy_to_text)
                  .pipe(shapely_to_text)
                  )
            df.to_csv(os.path.join(self._save_folder, f"{value}.csv"))

    def _load(self):
        if np.any([os.path.exists(os.path.join(self._save_folder, f"{v}.csv")) for (k, v) in
                   self._save_properties.items()]):
            self.log.info("Loading pre-computed attribute values.")
            for key, value in self._save_properties.items():
                if os.path.exists(os.path.join(self._save_folder, f"{value}.csv")):
                    self.log.debug(f"Loading {value}.csv into {key}.")
                    df = (pd.read_csv(os.path.join(self._save_folder, f"{value}.csv"), index_col=False)
                          .drop(columns=["Unnamed: 0"])
                          .pipe(text_to_ndarray)
                          .pipe(text_to_shapely)
                          )
                    setattr(self, key, df)
