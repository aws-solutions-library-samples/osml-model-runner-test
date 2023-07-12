#!/usr/bin/env python3

#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import argparse
import os
import subprocess

# grab local AWS creds
default_account = subprocess.check_output(
    "aws sts get-caller-identity --query Account --output text", shell=True, universal_newlines=True
).strip()

# set a default region if one isn't given in ENV
default_region = "us-west-2"

# set up a cli tool for the script using argparse
parser = argparse.ArgumentParser("process_image")
parser.add_argument("--image_bucket", help="The target image bucket to process with OSML Model Runner.", type=str)
parser.add_argument("--result_bucket", help="The target result bucket to store outputs from OSML Model Runner", type=str)
parser.add_argument("--model", help="The target model to use for object detection.", type=str, default="aircraft")
parser.add_argument("--processing_window", help="How long do we want to run the test for (in hours)", type=str)
parser.add_argument("--periodic_sleep", help="Periodically send a new image request (in seconds)", type=str, default="60")
parser.add_argument("--tile_format", help="The target tile format to use for tiling.", type=str)
parser.add_argument("--tile_compression", help="The compression used for the target image.", type=str)
parser.add_argument("--tile_size", help="The tile size to split the image into for model processing.", type=str)
parser.add_argument("--tile_overlap", help="The tile overlap to consider when processing regions.", type=str)
parser.add_argument("--region", help="The AWS region OSML is deployed to.", type=str, default=default_region)
parser.add_argument("--account", help="The AWS account OSML is deployed to.", type=str, default=default_account)
args = parser.parse_args()

# call into root directory of this package so that we can run this script from anywhere.
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# set the python path to include the project source
os.environ["PYTHONPATH"] = os.path.join(os.environ.get("PYTHONPATH", ""), "./src/")

if args.image_bucket:
    image_bucket = args.image_bucket
else:
    image_bucket: str = f"loadtest-images-{args.account}"

if args.result_bucket:
    result_bucket = args.result_bucket
else:
    result_bucket: str = f"loadtest-results-{args.account}"

# set the test input env variables
os.environ["ACCOUNT"] = args.account
os.environ["REGION"] = args.region
os.environ["TARGET_MODEL"] = args.model
os.environ["S3_SOURCE_IMAGE_BUCKET"] = image_bucket
os.environ["S3_LOAD_TEST_RESULT_BUCKET"] = result_bucket
os.environ["S3_RESULTS_BUCKET"] = result_bucket
os.environ["PERIODIC_SLEEP_SECS"] = args.periodic_sleep
os.environ["PROCESSING_WINDOW_HRS"] = args.processing_window

if args.tile_format:
    os.environ["TILE_FORMAT"] = args.tile_format
if args.tile_compression:
    os.environ["TILE_COMPRESSION"] = args.tile_compression
if args.tile_size:
    os.environ["TILE_SIZE"] = args.tile_size
if args.tile_overlap:
    os.environ["TILE_OVERLAP"] = args.tile_overlap

test = "src/aws/osml/load/load_test.py"

subprocess.run(["python3", "-m", "pytest", "-o", "log_cli=true", "-vv", test])
