import json

from ome_types.model import Channel, Channel_AcquisitionMode, Channel_ContrastMethod, Channel_IlluminationType, Color, \
    UnitsLength


class JSONChannelEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, Channel):
            return {
                'id':                         o.id,
                'name':                       o.name,
                'nd_filter':                  o.nd_filter,
                'pinhole_size':               o.pinhole_size,
                'pinhole_size_unit':          o.pinhole_size_unit,
                'pockel_cell_setting':        o.pockel_cell_setting,
                'samples_per_pixel':          o.samples_per_pixel,
                'acquisition_mode':           o.acquisition_mode,
                'annotation_refs':            o.annotation_refs,
                'color':                      o.color,
                'contrast_method':            o.contrast_method,
                'detector_settings':          o.detector_settings,
                'emission_wavelength':        o.emission_wavelength,
                'emission_wavelength_unit':   o.emission_wavelength_unit,
                'excitation_wavelength':      o.excitation_wavelength,
                'excitation_wavelength_unit': o.excitation_wavelength_unit,
                'filter_set_ref':             o.filter_set_ref,
                'fluor':                      o.fluor,
                'illumination_type':          o.illumination_type,
                'light_path':                 o.light_path,
                'light_source_settings':      o.light_source_settings
            }
        elif isinstance(o, Channel_AcquisitionMode):
            return o.value
        elif isinstance(o, Channel_ContrastMethod):
            return o.value
        elif isinstance(o, Channel_IlluminationType):
            return o.value
        elif isinstance(o, UnitsLength):
            return o.value
            # return o.value.encode('utf8')
        elif isinstance(o, Color):
            return o.as_named(fallback=True)
            # return o.as_rgb_tuple()

        # Let the base class default method raise the TypeError
        return super().default(o)
