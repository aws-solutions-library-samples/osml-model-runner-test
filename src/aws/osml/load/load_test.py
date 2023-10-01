#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import json
import logging
import sys
from datetime import datetime, timedelta
from threading import Thread
from time import sleep
from typing import Dict, List, Tuple, Union

import boto3
from botocore.exceptions import ClientError
from osgeo import gdal

from aws.osml.utils.clients import cw_client, s3_client, sm_client, sqs_client
from aws.osml.utils.integ_utils import build_image_processing_request, queue_image_processing_job
from aws.osml.utils.osml_config import OSMLConfig, OSMLLoadTestConfig

logger = logging.getLogger()
logger.setLevel(logging.INFO)

fh = logging.FileHandler("loadtest-{:%s}.log".format(datetime.now()))
fh.setLevel(logging.INFO)
logger.addHandler(fh)


class ImageRequestStatus(str):
    """
    Enumeration defining status for image
    """

    STARTED = "STARTED"
    PARTIAL = "PARTIAL"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


def get_cw_metrics(start_time: datetime) -> Tuple[int, int]:
    """
    Get total tiles processed and region processed from start time to now

    :param start_time: DateTime = start time of loadtest

    :return: Tuple[int, int] = total tiles and regions in tuple format
    """
    try:
        tiles_processed_response = cw_client().get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "tiles1",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "OSML",
                            "MetricName": "TilesProcessed",
                            "Dimensions": [{"Name": "ImageFormat", "Value": "TIFF"}],
                        },
                        "Period": 60,
                        "Stat": "Sum",
                    },
                },
            ],
            StartTime=start_time,
            EndTime=datetime.now(),
        )

        total_tiles_processed = sum(tiles_processed_response["MetricDataResults"][0]["Values"])

        regions_processed_response = cw_client().get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "regions1",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "OSML",
                            "MetricName": "RegionsProcessed",
                            "Dimensions": [{"Name": "ImageFormat", "Value": "TIFF"}],
                        },
                        "Period": 60,
                        "Stat": "Sum",
                    },
                },
            ],
            StartTime=start_time,
            EndTime=datetime.now(),
        )

        total_regions_processed = sum(regions_processed_response["MetricDataResults"][0]["Values"])

        return total_tiles_processed, total_regions_processed

    except ClientError as error:
        logger.error(f"Cannot fetch CloudWatch metric data - {error}")

    return 0, 0


def get_s3_images(bucket_name: str) -> Union[List[Dict[str, str]], None]:
    """
    Get all s3 images within the bucket

    :param bucket_name: str = name of the bucket

    :return: Dict[str, str] = a list of s3 images
    """
    try:
        response = s3_client().list_objects_v2(Bucket=bucket_name)

        images_list = []
        for image in response["Contents"]:
            image_name = f"s3://{bucket_name}/{image['Key']}"
            image_size = image["Size"]

            image_info = {"image_name": image_name, "image_size": image_size}

            # check if the extension is an image or not
            images_suffixes = (".ntf", ".nitf", ".tif", ".tiff", ".png", ".jpg", ".jpeg")
            if image_name.lower().endswith(images_suffixes):
                images_list.append(image_info)
            else:
                logger.warning(f"Invalid image extension! File: {image_name}, skipping...")

        if not images_list:
            return None

        return images_list
    except ClientError as error:
        logger.error(f"Error encountered attempting to access bucket: {bucket_name}")
        raise error


def check_s3_bucket(bucket_name: str) -> bool:
    """
    Check to see if the S3 Bucket exists

    :param bucket_name: str = name of the bucket

    :return: bool = does the bucket exist or not
    """
    try:
        s3_client().head_bucket(Bucket=bucket_name)
        return True
    except ClientError as error:
        logger.error(f"Error encountered attempting to access bucket: {bucket_name}")
        raise error


def get_model_instance_type(sm_model: str) -> str:
    """
    Get Model Instance Type

    :param sm_model: str = name of the SageMaker Model

    :return: str = model instance type
    """
    try:
        list_endpoints_response = sm_client().list_endpoint_configs(
            NameContains=f"MRTestingOSML{sm_model}ModelEndpointOSML{sm_model}Mode-",
        )

        endpoint_name = list_endpoints_response["EndpointConfigs"][0]["EndpointConfigName"]

        if endpoint_name:
            endpoint_config_response = sm_client().describe_endpoint_config(EndpointConfigName=endpoint_name)

            sm_instance_type = endpoint_config_response["ProductionVariants"][0]["InstanceType"]
            return sm_instance_type
        else:
            logger.error("The endpoint does not exist!")
    except ClientError as error:
        logger.error("Error encountered attempting to access SageMaker Model")
        raise error


def is_complete(job_status_dict: Dict) -> bool:
    total_image_processed = 0
    total_image_in_progress = 0
    total_image_failed = 0
    total_image_succeeded = 0
    for image_id, value in job_status_dict.items():
        if value["completed"]:
            total_image_processed += 1

            if value["status"] == ImageRequestStatus.SUCCESS:
                total_image_succeeded += 1
            elif value["status"] == ImageRequestStatus.FAILED or value["status"] == ImageRequestStatus.PARTIAL:
                total_image_failed += 1
        else:
            total_image_in_progress += 1
    if total_image_in_progress == 0:
        return True

    return False


def monitor_job_status(job_status_dict: Dict, expected_end_time: datetime, queue: boto3.resource) -> None:
    """
    Polls the messages from SQS, check every message in the SQS to determine the status of it. Then
    update the item in the job_status dict and goes on to the next one.

    :param queue: boto3.resource = the sqs client fixture passed in
    :param job_status_dict: Dict = dict containing job information
    :param expected_end_time: datetime = expected end time to end the thread

    :return: None
    """
    while True:
        if not job_status_dict:
            logger.info("[Background Thread] There's no images processing! Continuing...")
        else:
            logger.info(
                f"[Background Thread] There are {len(job_status_dict)} items... Checking the status of each items..."
            )
        try:
            while True:
                messages = queue.receive_messages()
                if len(messages) == 0:
                    break
                for message in messages:
                    message_attributes = json.loads(message.body).get("MessageAttributes", {})
                    message_image_id = message_attributes.get("image_id", {}).get("Value")
                    message_image_status = message_attributes.get("image_status", {}).get("Value")

                    if message_image_id in job_status_dict.keys():
                        # if the job already succeeded, we do not need to check, go to the next one
                        if not job_status_dict[message_image_id]["completed"]:
                            # update the status
                            job_status_dict[message_image_id]["status"] = message_image_status

                            # mark the item in the dict completed
                            if message_image_status in [
                                ImageRequestStatus.SUCCESS,
                                ImageRequestStatus.FAILED,
                                ImageRequestStatus.PARTIAL,
                            ]:
                                job_status_dict[message_image_id]["completed"] = True
                                job_status_dict[message_image_id]["processing_duration"] = (
                                        datetime.now() - job_status_dict[message_image_id]["start_time"]
                                )

                        # Delete received a message from queue once it has been processed
                        queue.delete_message(
                            ReceiptHandle=message['ReceiptHandle']
                        )
                    else:
                        logger.warning(f"[Background Thread] {message_image_id} does not exist in job_status_dict yet")
        except ClientError as error:
            logging.warning(f"[Background Thread] {error}")
        except KeyError as error:
            logging.warning(f"[Background Thread] {error}")

        if datetime.now() >= expected_end_time:
            if is_complete(job_status_dict):
                break

        sleep(5)


def display_image_results(job_status_dict: Dict, total_tiles_processed: int, total_regions_processed: int) -> Dict:
    """
    Calculate and display the result of LoadTest

    :param total_tiles_processed:
    :param total_regions_processed:
    :param job_status_dict: Dict = dict containing job information

    :return: None
    """
    total_image_sent = len(job_status_dict)
    total_image_in_progress = 0
    total_image_processed = 0
    total_image_failed = 0
    total_image_succeeded = 0
    total_size_processed = 0
    total_pixels_processed = (0, 0)

    for image_id, value in job_status_dict.items():
        if value["completed"]:
            total_image_processed += 1

            if value["status"] == ImageRequestStatus.SUCCESS:
                total_image_succeeded += 1
            elif value["status"] == ImageRequestStatus.FAILED or value["status"] == ImageRequestStatus.PARTIAL:
                total_image_failed += 1

            total_size_processed += value["size"]

            image_pixel = value["pixels"]
            total_pixels_processed = tuple(sum(item) for item in zip(total_pixels_processed, image_pixel))

        else:
            total_image_in_progress += 1

    # convert the size to GB
    total_size = "%.3f GB" % (total_size_processed / 1024 / 1024 / 1024)

    logger.info(
        f"""
            Total Images Sent: {total_image_sent}
            Total Images In-Progress: {total_image_in_progress}
            Total Images Processed: {total_image_processed}
            Total Images Succeeded: {total_image_succeeded}
            Total Images Failed: {total_image_failed}
            Total Size Processed: {total_size}
            Total Pixels Processed: {total_pixels_processed[0] * total_pixels_processed[1]}
            Total Tiles Processed: {total_tiles_processed}
            Total Regions Processed: {total_regions_processed}
            """
    )

    return {
        "total_image_sent": total_image_sent,
        "total_image_in_progress": total_image_in_progress,
        "total_image_processed": total_image_processed,
        "total_image_succeeded": total_image_succeeded,
        "total_image_failed": total_image_failed,
        "total_size_processed": total_size,
        "total_pixels_processed": total_pixels_processed,
        "total_tiles_processed": total_tiles_processed,
        "total_regions_processed": total_regions_processed,
    }


def start_workflow() -> None:
    """
    The workflow to build an image request for a specific SM endpoint and then place it
    on the corresponding SQS queue every defined seconds for ModelRunner to pick up and process.
    Once the image has been completed return the associated image_id and image_request object for analysis.
    Then it will display the results for all the images have been sent for ModelRunner and calculate
    how many has succeeded or failed.

    :return: None
    """

    # convert environment variables to variables
    s3_image_bucket = OSMLLoadTestConfig.S3_LOAD_TEST_SOURCE_IMAGE_BUCKET
    s3_result_bucket = OSMLLoadTestConfig.S3_LOAD_TEST_RESULT_BUCKET
    sm_endpoint_model = OSMLLoadTestConfig.SM_LOAD_TEST_MODEL
    sm_instance_type = get_model_instance_type(sm_endpoint_model)
    periodic_sleep = int(OSMLLoadTestConfig.PERIODIC_SLEEP_SECS)
    processing_window_min = int(OSMLLoadTestConfig.PROCESSING_WINDOW_MIN)

    # checking if images bucket exist and result bucket exist
    if not check_s3_bucket(s3_image_bucket) or not check_s3_bucket(s3_result_bucket):
        sys.exit(1)

    start_time = datetime.now()
    expected_end_time = start_time + timedelta(minutes=processing_window_min)

    logger.info(
        f"""Starting {start_time} the load test with the following parameters:
            Input S3 Image Bucket: {s3_image_bucket}
            Output S3 Result Bucket: {s3_result_bucket}
            SageMaker Instance Type: {sm_instance_type}
            SageMaker Model: {sm_endpoint_model}
            LoadTest will stop at {expected_end_time}, at least {processing_window_min} minutes from now
            """
    )

    job_status_dict = {}  # keep track of jobs and its status

    image_index = 0
    images_list = get_s3_images(s3_image_bucket)  # get list of images from the bucket

    if not images_list:
        logger.error(f"There's no images in {s3_image_bucket} bucket!")
        sys.exit(1)

    logger.info(f"There are {len(images_list)} images in {s3_image_bucket} bucket")

    # it will keep looping until the time is greater than expected_end_time, will stop
    # and generate cost_report after it
    job_summary_log_file = "logs/job_summary.json"
    job_status_log_file = "logs/job_summary.json"
    image_status_queue = None
    image_request_queue = None
    try:
        image_status_queue = sqs_client().get_queue_by_name(
            QueueName=OSMLConfig.SQS_IMAGE_STATUS_QUEUE, QueueOwnerAWSAccountId=OSMLConfig.ACCOUNT
        )
        image_request_queue = sqs_client().get_queue_by_name(
            QueueName=OSMLConfig.SQS_IMAGE_REQUEST_QUEUE, QueueOwnerAWSAccountId=OSMLConfig.ACCOUNT
        )
    except ClientError as error:
        logger.error(
            f"[Background Thread] Error encountered attempting to access SQS - {OSMLConfig.SQS_IMAGE_STATUS_QUEUE}")
        raise error

    # spinning up a daemon thread (aka monitoring the job status and keep tracking of it)
    daemon = Thread(target=monitor_job_status, args=(job_status_dict, expected_end_time, image_status_queue), daemon=True,
                    name="Background")
    daemon.start()
    while datetime.now() <= expected_end_time:
        while int(image_request_queue.attributes.get('ApproximateNumberOfMessagesVisible')) > 3:
            logger.info(f"ApproximateNumberOfMessagesVisible is greater than 3... waiting {periodic_sleep} seconds..")
            sleep(periodic_sleep)
        # build an image processing request
        image_url = images_list[image_index]["image_name"]
        image_size = images_list[image_index]["image_size"]
        image_processing_request = build_image_processing_request(sm_endpoint_model, image_url)

        # submit the image request to the SQS queue
        message_id = queue_image_processing_job(sqs_client(), image_processing_request)

        # grab the job id from the image request
        job_id = image_processing_request["jobId"]

        # get the pixel count (h x w)
        # gdal has this capability which allow to open file virtually without needing to download or pull in.
        gdal_info = gdal.Open(image_url.replace("s3:/", "/vsis3", 1))
        pixels = gdal_info.RasterXSize * gdal_info.RasterYSize

        # compile into dict format and store it in the list for future tracking
        job_status_dict[job_id] = {
            "image_url": job_id,
            "message_id": message_id,
            "status": ImageRequestStatus.STARTED,
            "completed": False,
            "size": image_size,
            "pixels": pixels,
            "start_time": datetime.now().strftime("%m/%d/%Y/%H:%M:%S"),
            "processing_duration": None,
        }

        logger.info(f"Total image sent {len(job_status_dict)}")

        image_index += 1

        # if we reached to the end, reset it back to zero
        # we would want to keep looping until the timer runs out
        if image_index == len(images_list):
            image_index = 0

        # occasionally display image results
        total_tiles_processed, total_regions_processed = get_cw_metrics(start_time)
        display_image_results(job_status_dict, total_tiles_processed, total_regions_processed)

        # Writing to sample.json
        with open(job_status_log_file, "w") as outfile:
            outfile.write(json.dumps(job_status_dict, indent=4))

    # ensure jobs completed
    while not is_complete(job_status_dict):
        # Writing to sample.json
        with open(job_status_log_file, "w") as outfile:
            outfile.write(json.dumps(job_status_dict, indent=4))
        display_image_results(job_status_dict, total_tiles_processed, total_regions_processed)
        logger.info(f"Waiting for jobs to complete...")
        sleep(5)

    actual_end_time = datetime.now()

    logger.info(f"Start time of execution: {start_time}")
    logger.info(f"Expected end time of execution: {expected_end_time}")
    logger.info(f"Actual end time of execution: {actual_end_time}")

    total_elapsed_time = actual_end_time - start_time
    logger.info(f"Total elapsed time: {total_elapsed_time.total_seconds()} seconds")

    # final display image results
    total_tiles_processed, total_regions_processed = get_cw_metrics(start_time)
    job_status_summary = display_image_results(job_status_dict, total_tiles_processed, total_regions_processed)
    # Writing final job_status.json
    with open(job_summary_log_file, "w") as outfile:
        outfile.write(json.dumps(job_status_summary, indent=4))


start_workflow()
