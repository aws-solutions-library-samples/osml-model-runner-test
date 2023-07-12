#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import logging

from aws.osml.utils import (
    OSMLConfig,
    count_features,
    ddb_client,
    kinesis_client,
    run_model_on_image,
    sqs_client,
    validate_expected_feature_count,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def test_model_runner_aircraft_model() -> None:
    """
    Run the test using the Aircraft and validate the number of features

    :return: None
    """

    # Launch our image request and validate it completes
    image_id, job_id, image_processing_request, kinesis_shard = run_model_on_image(
        sqs_client(), OSMLConfig.SM_AIRCRAFT_MODEL, kinesis_client()
    )

    # Count the features that were create in the table for this image
    feature_count = count_features(image_id=image_id, ddb_client=ddb_client())

    # Validate the number of features we created match expected values
    validate_expected_feature_count(feature_count)
