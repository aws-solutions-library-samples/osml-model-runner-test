#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import logging

from aws.osml.utils import (
    OSMLConfig,
    count_features,
    count_region_request_items,
    ddb_client,
    kinesis_client,
    run_model_on_image,
    sqs_client,
    validate_expected_feature_count,
    validate_expected_region_request_items,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def test_model_runner_flood_model() -> None:
    """
    Run the test using the FloodModel and validate the number of features
    and region requests

    :return: None
    """

    # Launch our image request and validate it completes
    image_id, job_id, image_processing_request, kinesis_shard = run_model_on_image(
        sqs_client(), OSMLConfig.SM_FLOOD_MODEL, "SM_ENDPOINT", kinesis_client()
    )

    # Count the features created in the table for this image
    feature_count = count_features(image_id=image_id, ddb_client=ddb_client())

    # Validate the number of features we created match expected values
    validate_expected_feature_count(feature_count)

    # Validate the number of region request that were created
    # in the process and check if they are succeeded
    region_request_count = count_region_request_items(image_id=image_id, ddb_client=ddb_client())

    validate_expected_region_request_items(region_request_count)
