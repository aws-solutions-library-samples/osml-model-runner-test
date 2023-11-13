#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import logging

from aws.osml.utils import OSMLConfig, kinesis_client, run_model_on_image, s3_client, sqs_client, validate_features_match

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def test_model_runner_aircraft_model() -> None:
    """
    Run the test using the Aircraft and validate the number of features

    :return: None
    """

    # Launch our image request and validate it completes
    image_id, job_id, image_processing_request, kinesis_shard = run_model_on_image(
        sqs_client(), OSMLConfig.SM_AIRCRAFT_MODEL, "SM_ENDPOINT", kinesis_client()
    )

    # Verify the results we created in the appropriate syncs
    validate_features_match(
        image_processing_request=image_processing_request,
        job_id=job_id,
        shard_iter=kinesis_shard,
        s3_client=s3_client(),
        kinesis_client=kinesis_client(),
    )
