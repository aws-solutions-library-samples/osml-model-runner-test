# Copyright 2023-2024 Amazon.com, Inc. or its affiliates.

"""
###################################################################################################

This script provides functionality to convert GeoTIFF images to NITF (National Imagery Transmission Format) format.
The script supports two target NITF formats: GREYSCALE (16bit) and WBID (Wideband Image Data).
It uses the GDAL (Geospatial Data Abstraction Library) library for the conversion process.

The script defines three main functions: 1. `Translate_to_greyscale`: Converts a GeoTIFF dataset to a greyscale NITF
format. 2. `Translate_to_WBID`: Converts a GeoTIFF dataset to a NITF file in the WBID format. 3.
`Convert_geotiff_to_nitf`: Converts GeoTIFF files in a specified input directory to the desired NITF format (either
greyscale or WBID) and saves them in an output directory.

The script accepts command-line arguments for specifying input and output directories, target format, inclusion of
XML metadata, and compression method.

Usage: python script_name.py --input_dir input_directory --output_format {GREYSCALE/WBID} [--output_dir
output_directory] [--include_xml {NO/YES}] [--compression compression_method]

Example Usage: python3 translate_images.py --input_dir input_data --output_format GREYSCALE --output_dir output_data
--include_xml YES --compression LZW

Please ensure you have the GDAL library and its Python bindings (osgeo.gdal) installed before running this script.
You can customize the script's behavior by modifying the function parameters and GDAL options as needed.
###################################################################################################"""

import argparse
import glob
import os
from enum import Enum, auto
from typing import Optional

from osgeo import gdal, gdalconst
from osgeo.gdal import Translate


class TargetFormat(Enum):
    """
    Enum for specifying the target NITF format for conversion.
    """

    GREYSCALE = auto()
    WBID = auto()


def translate_to_greyscale(out_file: str, ds: gdal.Dataset) -> gdal.Dataset:
    """
    Translate a GeoTIFF dataset to a greyscale NITF format.

    :param out_file: The path to the output NITF file to be created.
    :param ds: The input GeoTIFF dataset to be translated.
    :return: The translated NITF dataset.
    """
    return Translate(
        destName=out_file,
        srcDS=ds,
        bandList=[float(1)],
        format="NITF",
        outputType=gdalconst.GDT_Int16,
        creationOptions=["IC=C8", "PROFILE=NPJE_NUMERICALLY_LOSSLESS"],
    )


def translate_to_wbid(out_file: str, ds: gdal.Dataset) -> gdal.Dataset:
    """
    Converts a GeoTIFF dataset to a NITF file in the WBID format.

    :param out_file: The path to the output NITF file to be created.
    :param ds: The input GeoTIFF dataset to be converted.
    :return: The converted NITF dataset.
    """
    return Translate(
        destName=out_file,
        srcDS=ds,
        bandList=[1],
        format="NITF",
        outputType=gdalconst.GDT_Byte,
        creationOptions=["IC=C8", "PROFILE=NPJE_NUMERICALLY_LOSSLESS"],
    )


def convert_geotiff_to_nitf(input_dir: str, target_format: TargetFormat, output_dir: Optional[str] = None) -> None:
    """
    Convert GeoTIFF files in the input directory to NITF format (either greyscale or WBID).

    :param input_dir: The directory containing the input GeoTIFF files.
    :param target_format: The target format for conversion, either GREYSCALE or WBID.
    :param output_dir: The directory where converted NITF files will be saved.
                       If not provided, a default 'output' directory will be created
                       inside the input directory.
    :raises Exception: If an invalid target format is provided.
    """
    if output_dir is None:
        output_dir = os.path.join(input_dir, "output")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    input_files = glob.glob(os.path.join(input_dir, "*.tif"))

    for input_file in input_files:
        output_file = os.path.join(output_dir, os.path.splitext(os.path.basename(input_file))[0] + ".ntf")
        src_ds = gdal.Open(input_file)

        if target_format == TargetFormat.GREYSCALE:
            translate_to_greyscale(output_file, src_ds)
        elif target_format == TargetFormat.WBID:
            translate_to_wbid(output_file, src_ds)
        else:
            raise Exception(f"Invalid target format: {target_format}")

    print("Conversion completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert GeoTIFF images to a target NITF format.")
    parser.add_argument("input_dir", help="Input directory containing GeoTIFF images")
    parser.add_argument("--output_format", help="Target format to convert to (options: GREYSCALE/WBID)")
    parser.add_argument(
        "--output_dir", help="Output directory for NITF images (default: input_dir/output)", type=str, default=None
    )
    parser.add_argument(
        "--include_xml", help="Output directory for NITF images (default: NO, options: NO/YES)", type=str, default="NO"
    )
    parser.add_argument(
        "--compression", help="Target compression to use for imagery (default: NONE)", type=str, default=None
    )
    args = parser.parse_args()

    if args.compression is not None:
        gdal.SetConfigOption("COMPRESS_OVERVIEW", args.compression)

    gdal.SetConfigOption("GDAL_PAM_ENABLED", args.include_xml)

    usr_input_dir = args.input_dir
    usr_output_dir = args.output_dir

    convert_geotiff_to_nitf(usr_input_dir, TargetFormat[args.output_format], usr_output_dir)
