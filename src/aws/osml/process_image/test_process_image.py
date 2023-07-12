#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import logging

from aws.osml.utils import OSMLConfig, kinesis_client, run_model_on_image, sqs_client

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def test_process_image() -> None:
    """
    This runs a specified image against a target model and ensures
    we find a SUCCESS status for that image request.

    :return: None
    """
    # Launch our image request and validate it completes
    run_model_on_image(sqs_client(), OSMLConfig.TARGET_MODEL, kinesis_client())
