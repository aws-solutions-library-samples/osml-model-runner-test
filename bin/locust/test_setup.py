import boto3
from _image_job_status_monitor import ImageJobStatusMonitor
from locust import events

_shared_status_monitor = None


def get_shared_status_monitor():
    """
    Get the shared status monitor instance.

    There should only be one status monitor created for the entire test run as part of the Locust test_start
    event hook.

    :return: Shared ImageJobStatusMonitor instance
    """
    global _shared_status_monitor

    return _shared_status_monitor


@events.init_command_line_parser.add_listener
def add_custom_arguments(parser):
    """
    Add custom command line arguments for the load test.

    :param parser: ArgumentParser instance to add arguments to
    """
    parser.add_argument("--aws-account", type=str, default="", help="AWS Account ID")
    parser.add_argument(
        "--aws-region", type=str, env_var="AWS_DEFAULT_REGION", default="us-west-2", help="AWS Region for Testing"
    )
    parser.add_argument(
        "--mr-input-queue", type=str, default="ImageRequestQueue", help="Name of ModelRunner image request queue"
    )
    parser.add_argument(
        "--mr-status-queue", type=str, default="ImageStatusQueue", help="Name of ModelRunner image status queue"
    )
    parser.add_argument(
        "--test-imagery-location", type=str, default="s3://osml-test-images-<account>", help="S3 location of test images"
    )
    parser.add_argument(
        "--test-results-location", type=str, default="s3://mr-bucket-sink-<account>", help="S3 location of image results"
    )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Initialize test environment when the load test starts.

    Sets up monitoring and validates required configuration.

    :param environment: Locust environment instance
    :param kwargs: Additional keyword arguments
    :raises ValueError: If required configuration is missing
    """
    global _shared_status_monitor

    boto3.setup_default_session(region_name=environment.parsed_options.aws_region)

    if _shared_status_monitor is None:
        # Start the monitor background thread. This one thread will listen to the
        # SQS queue and keep track of all the status messages output by the system.
        # Note that this implementation currently prevents us from running Locust in
        # a distributed manner across multiple machines. That shouldn't be a problem
        # since the number of image requests sent (1000s/hour) should not put a
        # heavy load on the test driver but it is noted since this deviates from
        # common Locust test patterns.
        _shared_status_monitor = ImageJobStatusMonitor(
            status_queue_name=environment.parsed_options.mr_status_queue,
            status_queue_account=environment.parsed_options.aws_account,
            max_size=1000,
        )
        _shared_status_monitor.start()


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Clean up resources when the load test stops.

    Stops the status monitor and performs any other cleanup.

    :param environment: Locust environment instance
    :param kwargs: Additional keyword arguments
    """
    global _shared_status_monitor

    if _shared_status_monitor is not None:
        _shared_status_monitor.stop()
        _shared_status_monitor.join()
        _shared_status_monitor = None
