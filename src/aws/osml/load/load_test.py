#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from threading import Thread
from time import sleep
from typing import Dict, List, Union

from botocore.exceptions import ClientError
from osgeo import gdal

from aws.osml.utils.clients import s3_client, sm_client, sqs_client
from aws.osml.utils.integ_utils import build_image_processing_request, queue_image_processing_job
from aws.osml.utils.osml_config import OSMLConfig, OSMLLoadTestConfig

job_summary_log_file = "logs/job_summary.json"
job_status_log_file = "logs/job_status.json"
job_output_log_file = "logs/job_log.log"


logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger("botocore").setLevel(logging.CRITICAL)

# create the log file if it doesn't exist
if os.path.isfile(job_output_log_file):
    # Creates a new file
    with open(job_output_log_file, "w") as fp:
        pass
        # To write data to new file uncomment
        # this fp.write("New file created")

fh = logging.FileHandler(job_output_log_file)
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


def get_s3_images(bucket_name: str) -> Union[List[Dict[str, str]], None]:
    """
    Get all s3 images within the bucket to iterate through for load testing

    :param bucket_name: Name of source bucket to use for testing images

    :return: List of s3 images to process for load test
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

    :param bucket_name: Name of the bucket

    :return: True if the bucket exists, False otherwise
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

    :param sm_model: Name of the SageMaker Model

    :return: Model instance type
    """
    try:
        list_endpoints_response = sm_client().list_endpoint_configs(
            NameContains=f"{sm_model}",
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
    for image_id, value in job_status_dict.items():
        if value["completed"] is False:
            return False
    return True


def monitor_job_status(job_status_dict: Dict, expected_end_time: datetime) -> None:
    """
    Polls the messages from SQS, check every message in the SQS to determine the status of it. Then
    update the item in the job_status dict and go on to the next one.

    :param job_status_dict: Dict containing job information
    :param expected_end_time: Expected end time to end the thread

    :return: None
    """
    while True:
        if not job_status_dict:
            logger.debug("[Background Thread] There's no images processing! Waiting 5 seconds...")
            sleep(5)
            continue
        try:
            image_status_queue = sqs_client().get_queue_by_name(
                QueueName=OSMLConfig.SQS_IMAGE_STATUS_QUEUE, QueueOwnerAWSAccountId=OSMLConfig.ACCOUNT
            )
            while True:
                messages = image_status_queue.receive_messages()
                if len(messages) == 0:
                    break
                for message in messages:
                    message_attributes = json.loads(message.body).get("MessageAttributes", {})
                    message_image_id = message_attributes.get("image_id", {}).get("Value")
                    message_image_status = message_attributes.get("image_status", {}).get("Value")

                    if message_image_id in job_status_dict.keys():
                        if job_status_dict[message_image_id]["completed"] is False:
                            # update the status
                            job_status_dict[message_image_id]["status"] = message_image_status

                            # mark the item in the dict completed
                            if message_image_status in [
                                ImageRequestStatus.SUCCESS,
                                ImageRequestStatus.FAILED,
                                ImageRequestStatus.PARTIAL,
                            ]:
                                start_time = datetime.strptime(
                                    job_status_dict[message_image_id]["start_time"], "%m/%d/%Y/%H:%M:%S"
                                )
                                processing_duration = (datetime.now() - start_time).total_seconds()
                                job_status_dict[message_image_id]["completed"] = True
                                job_status_dict[message_image_id]["processing_duration"] = processing_duration
                    else:
                        logger.warning(f"[Background Thread] {message_image_id} does not exist in job_status_dict yet")
        except ClientError as error:
            logging.warning(f"[Background Thread] {error}")
        except KeyError as error:
            logging.warning(f"[Background Thread] {error}")

        if datetime.now() >= expected_end_time and is_complete(job_status_dict):
            logger.info("[Background Thread] All images have been processed!")
            break

        sleep(5)


def display_image_results(job_status_dict: Dict) -> Dict:
    """
    Calculate and display the result of LoadTest

    :param job_status_dict: Dictionary containing job information

    :return: Dict = dictionary containing the results
    """
    total_image_sent = len(job_status_dict)
    total_image_in_progress = 0
    total_image_processed = 0
    total_image_failed = 0
    total_image_succeeded = 0
    total_size_processed = 0
    total_pixels_processed = 0

    for image_id, value in job_status_dict.items():
        if value["completed"]:
            total_image_processed += 1

            if value["status"] == ImageRequestStatus.SUCCESS:
                total_image_succeeded += 1
            elif value["status"] == ImageRequestStatus.FAILED or value["status"] == ImageRequestStatus.PARTIAL:
                total_image_failed += 1

            total_size_processed += value["size"]

            total_pixels_processed += value["pixels"]

        else:
            total_image_in_progress += 1

    # convert the size to GB
    total_gb_processed = total_size_processed / 1024 / 1024 / 1024

    logger.info(
        f"""
            Total Images Sent: {total_image_sent}
            Total Images In-Progress: {total_image_in_progress}
            Total Images Processed: {total_image_processed}
            Total Images Succeeded: {total_image_succeeded}
            Total Images Failed: {total_image_failed}
            Total GB Processed: {total_gb_processed}
            Total Pixels Processed: {total_pixels_processed}
            """
    )

    return {
        "total_image_sent": total_image_sent,
        "total_image_in_progress": total_image_in_progress,
        "total_image_processed": total_image_processed,
        "total_image_succeeded": total_image_succeeded,
        "total_image_failed": total_image_failed,
        "total_gb_processed": total_gb_processed,
        "total_pixels_processed": total_pixels_processed,
    }


def start_workflow() -> None:
    """
    The workflow to build an image request for a specific SM endpoint and then place it
    on the corresponding SQS queue every defined second for ModelRunner to pick up and process.
    Once the image has been completed, return the associated image_id and image_request object for analysis.
    Then it will display the results for all the images have been sent for ModelRunner and calculate
    how many have succeeded or failed.

    :return: None
    """

    # convert environment variables to variables
    s3_image_bucket = OSMLLoadTestConfig.S3_LOAD_TEST_SOURCE_IMAGE_BUCKET
    s3_result_bucket = OSMLLoadTestConfig.S3_LOAD_TEST_RESULT_BUCKET
    sm_endpoint_model = OSMLLoadTestConfig.SM_LOAD_TEST_MODEL
    sm_instance_type = get_model_instance_type(sm_endpoint_model)
    periodic_sleep = int(OSMLLoadTestConfig.PERIODIC_SLEEP_SECS)
    processing_window_min = int(OSMLLoadTestConfig.PROCESSING_WINDOW_MIN)

    # checking if images bucket exists and result bucket exists
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
    images_list = get_s3_images(s3_image_bucket)  # get a list of images from the bucket

    if not images_list:
        logger.error(f"There's no images in {s3_image_bucket} bucket!")
        sys.exit(1)

    logger.info(f"There are {len(images_list)} images in {s3_image_bucket} bucket")

    # it will keep looping until the time is greater than expected_end_time, will stop
    # and generate cost_report after it is done
    # spinning up a daemon thread (aka monitoring the job status and keep tracking of it)
    daemon = Thread(target=monitor_job_status, args=(job_status_dict, expected_end_time), daemon=True, name="Background")
    daemon.start()
    while datetime.now() <= expected_end_time:
        image_request_queue = sqs_client().get_queue_by_name(
            QueueName=OSMLConfig.SQS_IMAGE_REQUEST_QUEUE, QueueOwnerAWSAccountId=OSMLConfig.ACCOUNT
        )
        while int(image_request_queue.attributes.get("ApproximateNumberOfMessages")) > 3:
            image_request_queue = sqs_client().get_queue_by_name(
                QueueName=OSMLConfig.SQS_IMAGE_REQUEST_QUEUE, QueueOwnerAWSAccountId=OSMLConfig.ACCOUNT
            )
            logger.info(f"ApproximateNumberOfMessages is greater than 3... waiting {periodic_sleep} seconds..")
            sleep(periodic_sleep)
        # build an image processing request
        image_url = images_list[image_index]["image_name"]
        image_size = images_list[image_index]["image_size"]
        image_processing_request = build_image_processing_request(sm_endpoint_model, image_url)

        # submit the image request to the SQS queue
        message_id = queue_image_processing_job(sqs_client(), image_processing_request)

        # grab the job id from the image request
        job_id = image_processing_request["jobId"]

        # gdal has this capability which allows to open file virtually without needing to download or pull in.
        gdal_info = gdal.Open(image_url.replace("s3:/", "/vsis3", 1))
        pixels = gdal_info.RasterXSize * gdal_info.RasterYSize
        image_id = job_id + ":" + image_url

        # compile into dict format and store it in the list for future tracking
        job_status_dict[image_id] = {
            "job_id": job_id,
            "image_url": image_url,
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

        # if we reached to the end, reset it back to zero,
        # we would want to keep looping until the timer runs out
        if image_index == len(images_list):
            image_index = 0

        # occasionally display image results
        display_image_results(job_status_dict)

        # Writing to job status file
        with open(job_status_log_file, "w") as outfile:
            outfile.write(json.dumps(job_status_dict, indent=4))

        sleep(1)

    # ensure jobs completed
    while not is_complete(job_status_dict):
        # Writing to sample.json
        with open(job_status_log_file, "w") as outfile:
            outfile.write(json.dumps(job_status_dict, indent=4))
        display_image_results(job_status_dict)
        logger.info("Waiting for jobs to complete...")
        sleep(5)

    actual_end_time = datetime.now()

    logger.info(f"Start time of execution: {start_time}")
    logger.info(f"Expected end time of execution: {expected_end_time}")
    logger.info(f"Actual end time of execution: {actual_end_time}")

    total_elapsed_time = actual_end_time - start_time
    logger.info(f"Total elapsed time: {total_elapsed_time.total_seconds()} seconds")

    # final display image results
    job_status_summary = display_image_results(job_status_dict)

    # Writing to job status file
    with open(job_status_log_file, "w") as outfile:
        outfile.write(json.dumps(job_status_dict, indent=4))

    # Writing final job_status.json
    with open(job_summary_log_file, "w") as outfile:
        outfile.write(json.dumps(job_status_summary, indent=4))

    logger.info(f"Load finished, completed in {total_elapsed_time.total_seconds()} seconds!")


start_workflow()
