#  Copyright 2023 Amazon.com, Inc. or its affiliates.

import logging

from aws.osml.utils import (
    OSMLConfig,
    count_features,
    count_region_request_items,
    ddb_client,
    elb_client,
    kinesis_client,
    run_model_on_image,
    s3_client,
    sqs_client,
    validate_expected_region_request_items,
    validate_features_match,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def test_model_runner_centerpoint_http_model() -> None:
    """
    Run the test using the CenterPointModel and validate the number of features
    and region requests using the HTTP endpoint

    :return: None
    """

    if OSMLConfig.HTTP_CENTERPOINT_MODEL_URL:
        http_endpoint_url = OSMLConfig.HTTP_CENTERPOINT_MODEL_URL
    else:
        http_endpoint_dns = get_load_balancer_dns_url(OSMLConfig.HTTP_CENTERPOINT_MODEL_ELB_NAME)
        http_endpoint_url = f"http://{http_endpoint_dns}{OSMLConfig.HTTP_CENTERPOINT_MODEL_INFERENCE_PATH}"

    # launch our image request and validate it completes
    image_id, job_id, image_processing_request, shard_iter = run_model_on_image(
        sqs_client(), http_endpoint_url, "HTTP_ENDPOINT", kinesis_client()
    )

    # count the created features in the table for this image
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


def get_load_balancer_dns_url(load_balancer_name: str) -> str:
    """
    Get the DNS URL for the given load balancer
    :param load_balancer_name: The name of the load balancer
    :return: The DNS URL for the load balancer
    """
    logger.debug("Retrieving DNS name for '{}'...".format(load_balancer_name))
    res = elb_client().describe_load_balancers(Names=[load_balancer_name])
    dns_name = res.get("LoadBalancers", [])[0].get("DNSName")
    logger.debug("Found DNS name: {}".format(dns_name))
    return dns_name
