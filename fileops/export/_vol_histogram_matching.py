import glob
import os

from skimage import io, exposure
from tifffile import imwrite, imread


def batch_match_volumetric_histograms(input_dir, output_dir, reference_idx=0):
    """
    Matches the intensity distribution of all 3D TIFF volumes in a directory
    to a single reference volume from that same directory.
    """
    # 1. Create output folder if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 2. Identify all TIFF files
    # Using sorted() ensures files are processed in temporal/numerical order
    file_list = sorted(glob.glob(os.path.join(input_dir, "*.tif*")))

    if not file_list:
        print(f"Error: No TIFF files found in {input_dir}")
        return

    # 3. Load the reference volume
    # In a timelapse, this is usually the first stable frame
    ref_path = file_list[reference_idx]
    print(f"Using {os.path.basename(ref_path)} as the intensity reference.")
    reference_vol = imread(ref_path)

    # 4. Process each volume
    for i, file_path in enumerate(file_list):
        filename = os.path.basename(file_path)

        # Skip matching if it's the reference file (just copy it)
        if i == reference_idx:
            imwrite(os.path.join(output_dir, filename), reference_vol, imagej=True, metadata={'order': 'ZCYX'})
            continue

        print(f"Matching intensities for: {filename}")

        # Load and match
        moving_vol = io.imread(file_path)

        # skimage.exposure.match_histograms handles 3D arrays automatically
        matched_vol = exposure.match_histograms(moving_vol, reference_vol)

        # Convert back to original bit-depth (e.g., uint16) to avoid float conversion
        matched_vol = matched_vol.astype(moving_vol.dtype)

        # Save output
        out_path = os.path.join(output_dir, filename)
        imwrite(out_path, matched_vol, imagej=True, metadata={'order': 'ZCYX'})

    print(f"\nSuccessfully processed {len(file_list)} volumes.")
