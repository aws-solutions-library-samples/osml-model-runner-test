#!/usr/bin/env python3

#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import argparse
import os
import subprocess

#
# This is a utility script for running tests against a known model runner deployment
#
# $1 = target_image = image to run test against
# $2 = target_model = model to run test against
# $3 = tile_format = optional tile format to use for processing
# $4 = tile_compression = optional tile compression to use for processing
#
# The user can also pass in a REGION and ACCOUNT parameter through setting the appropriate
# ENV variables in their local execution environment.
#
# Sample usage for processing an arbitrary image and looking for success:
# python3 process_image.py \
#   --image s3://test-images-409719124294/images/gis_test_2.tif \
#   --model aircraft \
#   --tile_format GTIFF \
#   --tile_compression NONE \
#   --tile_size 512
#
# add \
# --skip-integ
# if you want to skip running an integration test against the chosen model
#

# grab local AWS creds
default_account = subprocess.check_output(
    "aws sts get-caller-identity --query Account --output text", shell=True, universal_newlines=True
).strip()

# set a default region if one isn't given in ENV
default_region = "us-west-2"

# set up a cli tool for the script using argparse
parser = argparse.ArgumentParser("process_image")
parser.add_argument("--image", help="The target image URL to process with OSML Model Runner.", type=str, default="small")
parser.add_argument("--model", help="The target model to use for object detection.", type=str, default="centerpoint")
parser.add_argument("--skip_integ", help="Whether or not to compare image with known results.", action="store_true")
parser.add_argument("--tile_format", help="The target tile format to use for tiling.", type=str)
parser.add_argument("--tile_compression", help="The compression used for the target image.", type=str)
parser.add_argument("--tile_size", help="The tile size to split the image into for model processing.", type=str)
parser.add_argument("--tile_overlap", help="The tile overlap to consider when processing regions.", type=str)
parser.add_argument("--feature_selection_options", help="The feature selection options JSON string.", type=str)
parser.add_argument("--region", help="The AWS region OSML is deployed to.", type=str, default=default_region)
parser.add_argument("--account", help="The AWS account OSML is deployed to.", type=str, default=default_account)
args = parser.parse_args()

# standard test images deployed by CDK
image_bucket: str = f"test-images-{args.account}"
deployed_images: dict = {
    "small": f"s3://{image_bucket}/small.tif",
    "large": f"s3://{image_bucket}/large.tif",
    "meta": f"s3://{image_bucket}/meta.ntf",
    "tile_tif": f"s3://{image_bucket}/tile.tif",
    "tile_ntf": f"s3://{image_bucket}/tile.ntf",
    "tile_jpeg": f"s3://{image_bucket}/tile.jpeg",
    "tile_png": f"s3://{image_bucket}/tile.png",
    "sicd_capella_chip_ntf": f"s3://{image_bucket}/sicd-capella-chip.ntf",
    "sicd_umbra_chip_ntf": f"s3://{image_bucket}/sicd-umbra-chip.ntf",
    "sicd_interferometric_hh_ntf": f"s3://{image_bucket}/sicd-interferometric-hh.nitf"
}

# call into root directory of this package so that we can run this script from anywhere.
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# set the python path to include the project source
os.environ["PYTHONPATH"] = os.path.join(os.environ.get("PYTHONPATH", ""), "./src/")

# set the test input env variables
os.environ["ACCOUNT"] = args.account
os.environ["REGION"] = args.region
os.environ["TARGET_IMAGE"] = deployed_images.get(args.image, args.image)
os.environ["TARGET_MODEL"] = args.model
if args.tile_format:
    os.environ["TILE_FORMAT"] = args.tile_format
if args.tile_compression:
    os.environ["TILE_COMPRESSION"] = args.tile_compression
if args.tile_size:
    os.environ["TILE_SIZE"] = args.tile_size
if args.tile_overlap:
    os.environ["TILE_OVERLAP"] = args.tile_overlap
if args.feature_selection_options:
    os.environ["FEATURE_SELECTION_OPTIONS"] = args.feature_selection_options

# determine whether we are running output validation testing
if args.skip_integ:
    # process the given image and look for success w/o validating results
    test = "src/aws/osml/process_image/test_process_image.py"
else:
    # run integration test against known results
    test = f"src/aws/osml/integ/{args.model}/test_{args.model}_model.py"

subprocess.run(["python3", "-m", "pytest", "-o", "log_cli=true", "-vv", test])
