#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import json
import logging
import time
from secrets import token_hex
from typing import Any, Dict, List, Optional, Tuple

import boto3
import geojson
from boto3 import dynamodb
from botocore.exceptions import ClientError, ParamValidationError
from geojson import Feature

from .osml_config import OSMLConfig


def run_model_on_image(
    sqs_client: boto3.resource, endpoint: str, endpoint_type: str, kinesis_client: Optional[boto3.resource]
) -> Tuple[str, str, Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    The workflow to build an image request for a specific model endpoint and then place it
    on the corresponding SQS queue for ModelRunner to pick up and process. Once the image
    has been completed, return the associated image_id and image_request object for analysis.

    :param endpoint_type: The type of endpoint you want to build the image_request for SM/HTTP
    :param sqs_client: SQS client fixture passed in
    :param endpoint: endpoint you wish to run your image against
    :param kinesis_client: Optional kinesis client fixture passed in

    :return: Tuple[str, str, Dict[str, Any], Dict[str, Any]] = the generated image_id, job_id, image_request,
             and kinesis shard.
    """
    image_url = OSMLConfig.TARGET_IMAGE  # get image_url

    # Build an image processing request from the test environment
    image_processing_request = build_image_processing_request(endpoint, endpoint_type, image_url)

    # Get the current Kinesis shard iterator to listen to for results since our start time
    shard_iter = get_kinesis_shard(kinesis_client)

    # Submit the image request to the SQS queue
    queue_image_processing_job(sqs_client, image_processing_request)

    # Grab the job id from the image request
    job_id = image_processing_request["jobId"]

    # Recreate the image_id that will be associated with the image request
    # Note this logic must match the strategy used to construct the image ID in the Model Runner from the
    # image processing request. See AWSOversightMLModelRunner src/aws_oversightml_model_runner/model_runner_api.py
    image_id = job_id + ":" + image_processing_request["imageUrls"][0]

    # Monitor the job status queue for updates
    monitor_job_status(sqs_client, image_id)

    # Return the image id and generated request
    return image_id, job_id, image_processing_request, shard_iter


def queue_image_processing_job(sqs_client: boto3.resource, image_processing_request: Dict[str, Any]) -> Optional[str]:
    """
    Place an image_request object onto the associated SQS queue for ModelRunner
    pick up for processing.

    :param sqs_client: Sqs client fixture passed in
    :param image_processing_request: Image request to place in the queue.

    :return: None
    """
    logging.info(f"Sending request: jobId={image_processing_request['jobId']}")
    try:
        queue = sqs_client.get_queue_by_name(
            QueueName=OSMLConfig.SQS_IMAGE_REQUEST_QUEUE, QueueOwnerAWSAccountId=OSMLConfig.ACCOUNT
        )
        response = queue.send_message(MessageBody=json.dumps(image_processing_request))

        message_id = response.get("MessageId")
        logging.info(f"Message queued to SQS with messageId={message_id}")

        return message_id
    except ClientError as error:
        logging.error(f"Unable to send job request to SQS queue: {OSMLConfig.SQS_IMAGE_REQUEST_QUEUE}")
        logging.error(f"{error}")
        assert False

    except ParamValidationError as error:
        logging.error("Invalid SQS API request; validation failed")
        logging.error(f"{error}")
        assert False


def monitor_job_status(sqs_client: boto3.resource, image_id: str) -> None:
    """
    Monitors the status of the image request on the corresponding SQS queue and returns
    once the image request associated with the given image_id has completed.

    :param sqs_client: The sqs client fixture passed in
    :param image_id: Image_id associated with the image request to monitor
    :return: None
    """
    done = False
    # Let it wait 15 minutes before failing
    max_retries = 300
    retry_interval = 5
    queue = sqs_client.get_queue_by_name(
        QueueName=OSMLConfig.SQS_IMAGE_STATUS_QUEUE, QueueOwnerAWSAccountId=OSMLConfig.ACCOUNT
    )
    logging.info("Listening to SQS ImageStatusQueue for progress updates...")
    while not done and max_retries > 0:
        try:
            messages = queue.receive_messages()
            for message in messages:
                message_attributes = json.loads(message.body).get("MessageAttributes", {})
                message_image_id = message_attributes.get("image_id", {}).get("Value")
                message_image_status = message_attributes.get("image_status", {}).get("Value")
                if message_image_status == "IN_PROGRESS" and message_image_id == image_id:
                    logging.info("\tIN_PROGRESS message found! Waiting for SUCCESS message...")
                elif message_image_status == "SUCCESS" and message_image_id == image_id:
                    processing_duration = message_attributes.get("processing_duration", {}).get("Value")
                    assert float(processing_duration) > 0
                    done = True
                    logging.info(f"\tSUCCESS message found!  Image took {processing_duration} seconds to process")
                elif (
                    message_image_status == "FAILED" or message_image_status == "PARTIAL"
                ) and message_image_id == image_id:
                    failure_message = ""
                    try:
                        message = json.loads(message.body).get("Message", "")
                        failure_message = str(message)
                    except Exception:
                        pass
                    logging.info("Failed to process image. {}".format(failure_message))
                    assert False
                else:
                    logging.info("\t...")
        except ClientError as err:
            logging.warning(err)
            pass
        max_retries -= 1
        time.sleep(retry_interval)

    if not done:
        logging.info(f"Maximum retries reached waiting for {image_id}")
    assert done


def get_kinesis_shard(kinesis_client: boto3.client) -> Dict[str, Any]:
    """
    Get uniquely identified sequence of data records in a kinesis stream

    :param kinesis_client: boto3.client = the kinesis client fixture passed in

    :return: Dict[str, Any] = uniquely identified sequence of data records
    """

    # Set up a shard iterator to listen to Kinesis starting now
    stream_name = f"{OSMLConfig.KINESIS_RESULTS_STREAM_PREFIX}-{OSMLConfig.ACCOUNT}"
    stream_desc = kinesis_client.describe_stream(StreamName=stream_name)["StreamDescription"]
    return kinesis_client.get_shard_iterator(
        StreamName=stream_name, ShardId=stream_desc["Shards"][0]["ShardId"], ShardIteratorType="LATEST"
    )["ShardIterator"]


def validate_features_match(
    image_processing_request: Dict[str, Any],
    job_id: str,
    shard_iter: Dict[str, Any],
    s3_client: boto3.client = None,
    kinesis_client: boto3.client = None,
) -> None:
    """
    Compares known standard results (features) against the ones generated from the tests.

    :param image_processing_request: Dict[str, Any] = the image processing request to validate against
    :param job_id: str = the job-id associated with the request
    :param shard_iter: Dict[str, Any] = uniquely identified sequence of data records
    :param s3_client: boto3.client = the s3 client fixture passed in
    :param kinesis_client: boto3.client = the kinesis client fixture passed in

    :return: None
    """
    # Let it wait 2 minutes before failing
    max_retries = 24
    retry_interval = 5
    done = False

    result_file = f"./src/data/{OSMLConfig.TARGET_MODEL}.{OSMLConfig.TARGET_IMAGE.split('/')[-1]}.geojson"
    with open(result_file, "r") as geojson_file:
        expected_features = geojson.load(geojson_file)["features"]

    while not done and max_retries > 0:
        # This is really a List[Sink], but we don't have a common library to pull
        # this from so using "any"
        outputs: List[Dict[str, Any]] = image_processing_request["outputs"]
        # Reset found outputs on each retry so that we don't count a single output
        # multiple times and hit the success criteria without validating each output
        found_outputs = 0
        for output in outputs:
            if output["type"] == "S3":
                if validate_s3_features_match(output["bucket"], output["prefix"], expected_features, s3_client):
                    found_outputs = found_outputs + 1
            elif output["type"] == "Kinesis":
                if validate_kinesis_features_match(job_id, output["stream"], shard_iter, expected_features, kinesis_client):
                    found_outputs = found_outputs + 1
            if found_outputs == len(outputs):
                done = True
                logging.info(f"{found_outputs} output syncs validated, tests succeeded!")
            else:
                max_retries -= 1
                time.sleep(retry_interval)
                logging.info(f"Not all output syncs were validated, retrying. Retries remaining: {max_retries}")
    assert done


def validate_s3_features_match(bucket: str, prefix: str, expected_features: List[Feature], s3_client: boto3.client) -> bool:
    """
    Checks a s3 output sync against known good feature results for a given test image.

    :param bucket: Folder inside s3
    :param prefix: String of characters at the beginning of the object key name
    :param expected_features: The list of features
    :param s3_client: S3 client fixture passed in

    :return: True if S3 features match the expected features
    """
    logging.info(f"Checking S3 at '{bucket}/{prefix}' for results.")
    for object_key in get_matching_s3_keys(
        s3_client,
        bucket,
        prefix=prefix,
        suffix=".geojson",
    ):
        logging.info(f"Output: {object_key} found!")
        s3_output = s3_client.get_object(Bucket=bucket, Key=object_key)
        contents = s3_output["Body"].read()
        s3_features = geojson.loads(contents.decode("utf-8"))["features"]
        logging.info(f"S3 file contains {len(s3_features)} features")
        if feature_collections_equal(expected_features, s3_features):
            logging.info("S3 feature set matched expected features!")
            return True

    logging.info("S3 feature set didn't match expected features...")
    return False


def validate_kinesis_features_match(
    job_id: str,
    stream: str,
    shard_iter: Dict[str, Any],
    expected_features: List[Feature],
    kinesis_client: boto3.client,
) -> bool:
    """
    Checks a Kinesis output sync against know good feature results for a given test image

    :param job_id: Job-id associated with the request
    :param stream: Kinesis stream name
    :param shard_iter: Uniquely identified record sequence
    :param expected_features: List of features expected by test
    :param kinesis_client: Kinesis client fixture passed in

    :return: Kinesis features matches the expected features
    """
    logging.info(f"Checking Kinesis Stream '{stream}' for results.")
    records = kinesis_client.get_records(ShardIterator=shard_iter, Limit=10000)["Records"]
    kinesis_features = []
    for record in records:
        # Look for records that pertain to the target image_id
        if record["PartitionKey"] == job_id:
            kinesis_features.extend(geojson.loads(record["Data"])["features"])
        else:
            logging.warning(f"Found partition key: {record['PartitionKey']}")
            logging.warning(f"Looking for partition key: {job_id}")

    if feature_collections_equal(expected_features, kinesis_features):
        logging.info(f"Kinesis record contains expected {len(kinesis_features)} features!")
        return True

    logging.info("Kinesis feature set didn't match expected features...")
    return False


def get_matching_s3_keys(s3_client: boto3.client, bucket: str, prefix: str = "", suffix: str = "") -> None:
    """
    Generate the keys in an S3 bucket.

    :param s3_client: Boto3 S3 Client.
    :param bucket: Name of the S3 bucket.
    :param prefix: Only fetches keys that start with this prefix (optional).
    :param suffix: Only fetches keys that end with this suffix (optional).

    :return: None
    """
    kwargs = {"Bucket": bucket, "Prefix": prefix}
    while True:
        resp = s3_client.list_objects_v2(**kwargs)
        for obj in resp["Contents"]:
            key = obj["Key"]
            if key.endswith(suffix):
                yield key

        try:
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
        except KeyError:
            break


def feature_equal(expected: geojson.Feature, actual: geojson.Feature) -> bool:
    """
    Determines if two features are roughly equivalent. We can't compare the full object because
    each feature includes a hex token as a top level property. Instead, we compare every other part of
    the feature to make sure they match. The expected data located in ./src/data has a placeholder
    value, $IMAGE_ID$, in place of an actual image id so that we can swap it in.

    :param expected: Feature we expect to match the result
    :param actual: Feature that was generated by the test

    :return: Whether the features match
    """
    actual_pixel_coords = actual.get("properties", {}).get("detection", {}).get("pixelCoordinates")
    expected_pixel_coords = expected.get("properties", {}).get("detection", {}).get("pixelCoordinates")
    return (
        expected.type == actual.type
        and expected.geometry == actual.geometry
        and expected_pixel_coords == actual_pixel_coords
        and expected.properties.get("inferenceMetadata") is not None
        and expected.properties.get("source") == actual.properties.get("source")
        and expected.properties.get("detection") == actual.properties.get("detection")
        and expected.properties.get("center_longitude") == actual.properties.get("center_longitude")
        and expected.properties.get("center_latitude") == actual.properties.get("center_latitude")
    )


def feature_collections_equal(expected: List[geojson.Feature], actual: List[geojson.Feature]) -> bool:
    """
    Determines whether the supplied unordered feature lists are equal

    :param expected: An unordered list of expected features
    :param actual: An unordered list of detected features

    :return: Check to see if expected and actual are equal
    """
    if not len(expected) == len(actual):
        logging.info(f"Expected {len(expected)} features but found {len(actual)}")
        return False
    # The order of features will depend on the order that regions/tiles were fed to the model.
    # While the order should roughly be the same, there isn't a guarantee, we're just checking
    # that all expected features were detected here as order within the collection isn't
    # actually important.
    expected.sort(key=lambda x: str(x.get("properties", {}).get("detection", {}).get("pixelCoordinates")))
    actual.sort(key=lambda x: str(x.get("properties", {}).get("detection", {}).get("pixelCoordinates")))
    for expected_feature, actual_feature in zip(expected, actual):
        if not feature_equal(expected_feature, actual_feature):
            logging.info(expected_feature)
            logging.info("does not match actual")
            logging.info(actual_feature)
            return False
    return True


def build_image_processing_request(endpoint: str, endpoint_type: str, image_url: str) -> Dict[str, Any]:
    """
    Build an image_processing_request meant to be placed on the corresponding ModelRunner SQS queue.
    The image request is configured from test environment.
    In the future this could, and probably should, be extended to build more variant image requests for additional
    testing configurations.

    :param endpoint_type: The type of endpoint you want to build the image_request for SM/HTTP
    :param image_url: URL to the image you want to process
    :param endpoint: Model endpoint that you want to build the image_request for

    :return: Dictionary representation of the image request
    """
    if OSMLConfig.KINESIS_RESULTS_STREAM:
        result_stream = OSMLConfig.KINESIS_RESULTS_STREAM
    else:
        result_stream = f"{OSMLConfig.KINESIS_RESULTS_STREAM_PREFIX}-{OSMLConfig.ACCOUNT}"

    if OSMLConfig.S3_RESULTS_BUCKET:
        result_bucket = OSMLConfig.S3_RESULTS_BUCKET
    else:
        result_bucket = f"{OSMLConfig.S3_RESULTS_BUCKET_PREFIX}-{OSMLConfig.ACCOUNT}"

    logging.info(f"Starting ModelRunner image job in {OSMLConfig.REGION}")
    logging.info(f"Image: {image_url}")
    logging.info(f"Model: {endpoint}, Type:{endpoint_type}")

    job_id = token_hex(16)
    job_name = f"test-{job_id}"
    logging.info(f"Creating request job_id={job_id}")

    image_processing_request: Dict[str, Any] = {
        "jobArn": f"arn:aws:oversightml:{OSMLConfig.REGION}:{OSMLConfig.ACCOUNT}:ipj/{job_name}",
        "jobName": job_name,
        "jobId": job_id,
        "imageUrls": [image_url],
        "outputs": [
            {"type": "S3", "bucket": result_bucket, "prefix": f"{job_name}/"},
            {"type": "Kinesis", "stream": result_stream, "batchSize": 1000},
        ],
        "imageProcessor": {"name": endpoint, "type": endpoint_type},
        "imageProcessorTileSize": OSMLConfig.TILE_SIZE,
        "imageProcessorTileOverlap": OSMLConfig.TILE_OVERLAP,
        "imageProcessorTileFormat": OSMLConfig.TILE_FORMAT,
        "imageProcessorTileCompression": OSMLConfig.TILE_COMPRESSION,
        "featureSelectionOptions": OSMLConfig.FEATURE_SELECTION_OPTIONS,
    }

    return image_processing_request


def count_features(image_id: str, ddb_client: boto3.resource) -> int:
    """
    Counts the features present in the given DDB table associated
    with an image_id (hash_key)

    :param image_id: Image_id features are associated with
    :param ddb_client: DDB client fixture

    :return: Count of the features found in the table for the image id
    """
    ddb_table = ddb_client.Table(OSMLConfig.DDB_FEATURES_TABLE)

    # Query the database for all items with the given image_id (hash_key)
    logging.info(f"Counting DDB items for image {image_id}...")
    items = query_items(ddb_table, "hash_key", image_id)

    # Go through our items and group our features per tile
    features: List[Feature] = []
    for item in items:
        for feature in item["features"]:
            features.append(geojson.loads(feature))

    # Count the features we found and report them up
    total_features = len(features)
    logging.info(f"Found {total_features} features!")
    return total_features


def validate_expected_feature_count(feature_count: int) -> None:
    """
    Validate the number of features created match expected values

    :param feature_count: Number of features found for an image

    :return: None
    """
    expected_feature_count = get_expected_image_feature_count(OSMLConfig.TARGET_IMAGE)
    test_succeeded = False
    if feature_count == expected_feature_count:
        logging.info(f"Found expected features for image {OSMLConfig.TARGET_IMAGE}.")
        test_succeeded = True
    else:
        logging.info(f"Found {feature_count} features for image but expected {expected_feature_count}!")

    assert test_succeeded


def get_expected_image_feature_count(image: str) -> int:
    """
    Get the number of expected features that are created for each image,
    since these are random.
    We want to just count the features in the table,
    not match them against any known results.

    :return: Features we expect for a given image using the flood model
    """
    # Set the expected
    if "large" in image:
        return 112200
    elif "tile" in image:
        return 2
    elif "sicd-capella-chip" in image or "sicd-umbra-chip" in image:
        return 100
    elif "sicd-interferometric" in image:
        return 15300
    else:
        raise Exception(f"Could not determine expected features for image: {image}")


def query_items(ddb_table: boto3.resource, hash_key: str, hash_value: str) -> List[Dict[str, Any]]:
    """
    Query the table for all items of a given hash_key and hash_value.

    :param ddb_table: DynamoDB table you wish to query
    :param hash_key: The Hash key associated with the items you wish to scan
    :param hash_value: The Hash key value of the items you wish to scan

    :return: List[Dict[str, Any]] = the list of dictionary responses corresponding to the items returned
    """
    all_items_retrieved = False
    response = ddb_table.query(
        ConsistentRead=True,
        KeyConditionExpression=dynamodb.conditions.Key(hash_key).eq(hash_value),
    )

    # Grab all the items from the table
    items: List[dict] = []
    while not all_items_retrieved:
        items.extend(response["Items"])

        if "LastEvaluatedKey" in response:
            response = ddb_table.query(
                ConsistentRead=True,
                KeyConditionExpression=dynamodb.conditions.Key(hash_key).eq(hash_value),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
        else:
            all_items_retrieved = True

    return items


def count_region_request_items(image_id: str, ddb_client: boto3.resource) -> int:
    """
    Counts the region request present in the given DDB table associated
    with an image_id (hash_key)

    :param image_id: Image_id region request is associated with
    :param ddb_client: DDB client fixture

    :return: Count of the region request found in the table for the image id
    """
    ddb_region_request_table = ddb_client.Table(OSMLConfig.DDB_REGION_REQUEST_TABLE)
    items = query_items(ddb_region_request_table, "image_id", image_id)

    total_count = 0
    for item in items:
        if item["region_status"] == "SUCCESS":
            total_count += 1
    logging.info(f"Found {total_count} Succeeded Region Request Items!")

    return total_count


def validate_expected_region_request_items(region_request_count: int) -> None:
    """
    Validate the number of region requests created match-expected values

    :param region_request_count: Number of region requests found for an image

    :return: None
    """
    expected_count = get_expected_region_request_count(OSMLConfig.TARGET_IMAGE)
    test_succeeded = False
    if region_request_count == expected_count:
        logging.info(f"Found expected region request for image {OSMLConfig.TARGET_IMAGE}.")
        test_succeeded = True
    else:
        logging.info(f"Found {region_request_count} region request for image but expected {expected_count}!")

    assert test_succeeded


def get_expected_region_request_count(image: str) -> int:
    """
    Get the expected number of region requests was created for each image

    :return: Region request we expect for a given image using the flood model
    """
    expected_count = 0
    if "small" in image:
        expected_count = 1
    elif "meta" in image:
        expected_count = 1
    elif "large" in image:
        expected_count = 49
    elif "tile" in image:
        expected_count = 1
    elif "sicd-capella-chip" in image or "sicd-umbra-chip" in image:
        expected_count = 1
    elif "sicd-interferometric" in image:
        expected_count = 8
    elif "wbid" in image:
        expected_count = 1

    # Check that we got a valid region request count
    if expected_count != 0:
        return expected_count
    else:
        raise Exception(f"Could not determine expected region request for image: {image}")
