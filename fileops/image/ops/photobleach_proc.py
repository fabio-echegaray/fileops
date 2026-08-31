from __future__ import annotations

import itertools
import os
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from fileops.image.imagemeta import metadataimage_like
from fileops.image.ops import bleach_func, photobleach_fit, ImageProcessor, z_projection

if TYPE_CHECKING:
    from fileops.image import ImageFile, MetadataImage


class PhotoBleachProcessor(ImageProcessor):
    """ performs photobleach correction of z-projected frames """

    def __init__(self, *args, **kwargs):
        self: ImageFile
        super().__init__(*args, **kwargs)

        self.photobleach_dict = {
            "data":  [],
            "model": {
                "status":  "init",
                "channel": {}
            }
        }

        # internal variables
        self._pb_frames_left = None
        self._pb_channels_left = None
        self._pb_df = None

    def precalc(self):
        if self.photobleach_dict["model"]["status"] == "ready":
            return
        for f, c in itertools.product(self.imf.frames, self.imf.channels):
            mdiz = z_projection(self.imf, f, c)
            self.calc_stats_of_timepoint(mdiz)

    def on_added(self, imf: ImageFile):
        self.imf = imf
        self.log.info(f"Adding photobleach correction to {self.imf.image_path}.")

        self._pb_frames_left = set(self.imf.frames)
        self._pb_channels_left = set(self.imf.channels)

        if self.construct_data():
            self.photobleach_correct()

    def calc_stats_of_timepoint(self, mdi: MetadataImage):
        with open(self.imf.base_path / f"photobleach_s{self.imf.series_id}.safe_to_delete.temp", "at") as f:
            f.write(",".join([str(mdi.channel),
                              str(mdi.frame),
                              str(np.min(mdi.image)),
                              str(np.max(mdi.image)),
                              str(np.std(mdi.image)),
                              str(np.mean(mdi.image)),
                              str(np.mean(mdi.image))]))
            f.write("\n")

    def process(self, mdi: MetadataImage, *args, **kwargs) -> 'MetadataImage':
        if (self.photobleach_dict["model"]["status"] == "ready"
                and mdi.channel in self.photobleach_dict["model"]["channel"]
                and self.photobleach_dict["model"]["channel"][mdi.channel] is not None):
            pb_a, pb_b, pb_c = self.photobleach_dict["model"]["channel"][mdi.channel]

            # compute how much we need to add to image in terms of mean field differences
            dfc = self._pb_df.query(f"channel=={mdi.channel}")
            avg_i0 = float(dfc.iloc[0]["mean"])
            delta_i = int(avg_i0 - pb_c) - int(pb_a) * np.exp(-np.round(pb_b, 4) * mdi.frame)

            corrected_img = mdi.image + np.array(delta_i).astype(mdi.image.dtype)
            mdi_corrected = metadataimage_like(mdi, corrected_img)
            return mdi_corrected
        else:
            # add time point
            self.calc_stats_of_timepoint(mdi)
            return mdi

    def construct_data(self):
        data_ch = {ch: [] for ch in self.imf.channels}
        for ch in self.imf.channels:
            df_ch_path = self.imf.base_path / f"photobleach_s{self.imf.series_id}ch{ch:02d}.safe_to_delete.xlsx"
            if df_ch_path.exists():
                # if path is found, load data and fit function
                df_ch = pd.read_excel(df_ch_path).sort_values(by=["channel", "frame"])
                if df_ch["frame"].max() + 1 < self.imf.n_frames:
                    os.remove(df_ch_path)
                else:
                    data_ch[ch].extend(df_ch.to_dict('records'))

        # add newly calculated data
        if (data_tmp_path := self.imf.base_path / f"photobleach_s{self.imf.series_id}.safe_to_delete.temp").exists():
            pb_df = (pd.read_csv(data_tmp_path, names=["channel", "frame", "min", "max", "std", "mean", "sum"])
                     .sort_values(by=["channel", "frame"])
                     .drop_duplicates())
            for ch in self.imf.channels:
                if len(df_ch := pb_df.query(f"channel=={ch}")) == self.imf.n_frames:
                    data_ch[ch].extend(df_ch.to_dict('records'))
            # finally, remove temporary file
            os.remove(data_tmp_path)

        for ch in self.imf.channels:
            self.photobleach_dict["data"].extend(data_ch[ch])

        return True

    def photobleach_correct(self):
        self.log.info("Fitting function for photobleach correction.")

        if self._pb_df is None:
            if (data_len := len(self.photobleach_dict["data"])) < self.imf.n_frames:
                self.photobleach_dict["model"]["status"] = "not enough data"
                return

            self._pb_df = pd.DataFrame(self.photobleach_dict["data"]).sort_values(by=["channel", "frame"])

        if len(self._pb_df) == 0:  # no data to fit a curve
            self.photobleach_dict["model"]["status"] = "not enough data"
            return

        for ch in self.imf.channels:
            dfc = self._pb_df.query(f"channel=={ch}").drop_duplicates(subset=["frame"])
            if len(dfc) == 0:  # no data to fit a curve
                continue

            df_ch_path = self.imf.base_path / f"photobleach_s{self.imf.series_id}ch{ch:02d}.safe_to_delete.xlsx"
            dfc.to_excel(df_ch_path, index=False)

            pbparms = photobleach_fit(dfc["mean"])
            self.photobleach_dict["model"]["channel"][ch] = pbparms

            plot_path = self.imf.base_path / f'photobleach_s{self.imf.series_id}ch{ch:01d}.safe_to_delete.pdf'
            if not plot_path.exists():
                plot_photobleach_curve(dfc, pbparms, save_path=plot_path)

        self.photobleach_dict["model"]["status"] = "ready"


# --------------------------------------------------------------------------------------------------------------
#  Plot the curve fit with de-trended data
# --------------------------------------------------------------------------------------------------------------
def plot_photobleach_curve(df, photobleach_parms, save_path=None):
    frames = df["frame"]
    intensities = df["mean"]
    errors = df["std"]

    f = plt.figure()
    ax = f.gca()
    ax.plot(frames, intensities, c='b', lw=0.1, label='Mean Intensity')
    ax.errorbar(frames, intensities, yerr=errors, c='b', fmt='.', lw=0.1, ms=0.1, label='Mean Intensity')

    pb_a, pb_b, pb_c = photobleach_parms
    dtrend = int(intensities.tolist()[0] - pb_c) - int(pb_a) * np.exp(-np.round(pb_b, 4) * frames)
    ax.scatter(frames, intensities + dtrend, c='k', s=0.1, label='Corrected Intensity')

    ax.plot(frames, bleach_func(frames, *photobleach_parms), 'r-', zorder=10,
            label='fit: a=%5.3f, b=%5.3f, c=%5.3f' % tuple(photobleach_parms))
    ax.plot(frames, dtrend, 'y-', zorder=10, label='Values Added')
    ax.text(0.7, .1, r"$f(x)=a \cdot e^{-b \cdot x} +c$", color="k", fontsize=10, transform=ax.transAxes)

    ax.set_xlabel('Frame')
    ax.set_ylabel('Avg. Intensity [au]')
    ax.legend()
    if save_path is not None:
        f.savefig(save_path)
