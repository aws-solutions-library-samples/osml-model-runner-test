#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import logging

from aws.osml.utils import (
    OSMLConfig,
    count_features,
    count_region_request_items,
    ddb_client,
    kinesis_client,
    run_model_on_image,
    s3_client,
    sqs_client,
    validate_expected_region_request_items,
    validate_features_match,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def test_model_runner_center_point_model() -> None:
    """
    Run the test using the CenterPointModel and validate the number of features
    and region requests

    :return: None
    """

    # launch our image request and validate it completes
    image_id, job_id, image_processing_request, shard_iter = run_model_on_image(
        sqs_client(), OSMLConfig.SM_CENTERPOINT_MODEL, "SM_ENDPOINT", kinesis_client()
    )

    # count the features created in the table for this image
    count_features(image_id=image_id, ddb_client=ddb_client())

    # verify the results we created in the appropriate syncs
    validate_features_match(
        image_processing_request=image_processing_request,
        job_id=job_id,
        shard_iter=shard_iter,
        s3_client=s3_client(),
        kinesis_client=kinesis_client(),
    )

    # validate the number of region requests that were created in the process and check if they are succeeded
    region_request_count = count_region_request_items(image_id=image_id, ddb_client=ddb_client())
    validate_expected_region_request_items(region_request_count)
