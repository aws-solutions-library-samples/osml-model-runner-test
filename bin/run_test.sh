#!/bin/bash

#
# Copyright 2023 Amazon.com, Inc. or its affiliates.
#

# This is a utility script to help building and uploading the OSML default test model to an accounts ECR
# repository deployed by the AWSOversightMLCDK package. While this script can be run without providing inputs,
# a user can pass in the following optional parameters to modify default behavior:
# $1 = test_image = image to run test against
# $2 = MODEL = options: < centerpoint | flood | process | aircraft >
# $2 = test_tile_format = tile format to use
# $3 = test_tile_compression = tile compression to use
# $4 = region = region OSML is deployed in
# $5 = account = account to test with
# $6 = remote account = see description below

# If you want to test cross account access provide a remote account (ex. 555986723962)
# If the value is set it will use images from the gamma integ account
# and will write results to the stream and bucket located in that account
# You'll need to run the tests using creds for the gamma deployment account or
# add your account as a trusted principal to the necessary roles in the remote account


# Grab user inputs or set default values
export TARGET_IMAGE=${1}
export MODEL=${2:-centerpoint}
export TEST_TILE_FORMAT=${3:-NITF}
export TEST_TILE_COMPRESSION=${4:-J2K}
export REGION=${5:-us-west-2}
export ACCOUNT=${6:-$(aws sts get-caller-identity --query Account --output text)}
export REMOTE_ACCOUNT=${7:-}

# Standard test images deployed by CDK currently
case $TARGET_IMAGE in
  "small")
    TARGET_IMAGE="s3://test-images-${ACCOUNT}/small.tif"
    ;;

  "large")
    TARGET_IMAGE="s3://test-images-${ACCOUNT}/large.tif"
    TEST_TILE_COMPRESSION=NONE
    ;;

  "meta")
    TARGET_IMAGE="s3://test-images-${ACCOUNT}/meta.ntf"
    ;;

  "tile_tif")
    TARGET_IMAGE="s3://test-images-${ACCOUNT}/tile.tif"
    ;;

  "tile_ntf")
    TARGET_IMAGE="s3://test-images-${ACCOUNT}/tile.ntf"
    ;;

  "tile_jpeg")
    TARGET_IMAGE="s3://test-images-${ACCOUNT}/tile.jpeg"
    ;;

  "tile_png")
    TARGET_IMAGE="s3://test-images-${ACCOUNT}/tile.png"
    ;;

  "sicd_capella_chip_ntf")
    TARGET_IMAGE="s3://test-images-${ACCOUNT}/sicd-capella-chip.ntf"
    TEST_TILE_COMPRESSION=NONE
    ;;

  "sicd_umbra_chip_ntf")
    TARGET_IMAGE="s3://test-images-${ACCOUNT}/sicd-umbra-chip.ntf"
    TEST_TILE_COMPRESSION=NONE
    ;;

  "sicd_interferometric_hh_ntf")
    TARGET_IMAGE="s3://test-images-${ACCOUNT}/sicd-interferometric-hh.nitf"
    TEST_TILE_COMPRESSION=NONE
    ;;

esac

# Expected values from our CDK package
export IMAGE_QUEUE_NAME=ImageRequestQueue
export TEST_RESULTS_BUCKET=test-results-${ACCOUNT}
export TEST_STREAM=test-stream-${ACCOUNT}
export JOB_STATUS_TABLE=ImageProcessingJobStatus
export REGION_REQUEST_TABLE=RegionProcessingJobStatus
export FEATURE_TABLE=ImageProcessingFeatures
export SM_CENTER_POINT_MODEL=centerpoint
export SM_FLOOD_MODEL=flood
export SM_AIRCRAFT_MODEL=aircraft
export TILE_FORMAT=${TEST_TILE_FORMAT}
export TILE_COMPRESSION=${TEST_TILE_COMPRESSION}
export TEST_STATUS_QUEUE=ImageStatusQueue
export TARGET_MODEL=${MODEL}

# Call into root directory of this pacakge so that we can
# run this script from anywhere.
LOCAL_DIR="$( dirname -- "$0"; )"
cd "${LOCAL_DIR}/.." || exit 1

export PYTHONPATH="${PYTHONPATH}:./src/"

# Run integration tests with pytest
time python3 -m pytest -o log_cli=true -vv src/aws/osml/integ/"${MODEL}"/test_"${MODEL}"_model.py
