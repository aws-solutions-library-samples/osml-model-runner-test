import json
import logging
from collections import OrderedDict
from threading import Lock, Thread
from typing import Optional

import boto3

logger = logging.getLogger(__name__)


class ImageJobStatusMonitor(Thread):
    """
    Monitor the status of image processing jobs by polling an SQS queue.

    The expectation is that a given test will only have a single instance of this thread running as a background
    process. That process will aggregate wll of the image statuses and make them available to any ModelRunnerUser
    instances that need to check the status of a job they submitted.

    :param status_queue_name: Name of the SQS queue to monitor
    :param status_queue_account: AWS account ID containing the SQS queue
    :param max_size: Maximum size of the status cache
    """

    def __init__(self, status_queue_name: str, status_queue_account: str, max_size: int = 1000):
        super().__init__()
        self.status_queue_name = status_queue_name
        self.status_queue_account = status_queue_account
        self.running = False
        self.job_status_cache = OrderedDict()
        self.job_status_cache_lock = Lock()
        self.max_size = max_size

    def run(self) -> None:
        """
        Main thread loop that continuously polls the SQS queue for job status updates.

        Updates the internal cache with job statuses received from the queue.
        """
        try:
            sqs_service_resource = boto3.resource("sqs")
            queue = sqs_service_resource.get_queue_by_name(
                QueueName=self.status_queue_name, QueueOwnerAWSAccountId=self.status_queue_account
            )

            logger.info(f"Started monitoring {self.status_queue_name} for image status messages")
            self.running = True
            while self.running:
                messages = queue.receive_messages()
                for message in messages:
                    message_attributes = json.loads(message.body).get("MessageAttributes", {})
                    message_job_id = message_attributes.get("job_id", {}).get("Value")
                    message_status = message_attributes.get("status", {}).get("Value")
                    processing_duration = message_attributes.get("processing_duration", {}).get("Value", None)

                    logger.info(f"STATUS MONITOR: {message_job_id}:{message_status}:{processing_duration}")
                    current_status, current_duration = (None, None)
                    with self.job_status_cache_lock:
                        if message_job_id in self.job_status_cache:
                            current_status, current_duration = self.job_status_cache[message_job_id]

                        if current_status not in ["SUCCESS", "FAILED"] or (
                            current_status == "PARTIAL" and message_status in ["SUCCESS", "FAILED"]
                        ):
                            # We had an earlier status but it was not final, remove it
                            if message_job_id in self.job_status_cache:
                                self.job_status_cache.pop(message_job_id)

                            # If the cache is at capacity remove the first(oldest) status
                            if len(self.job_status_cache) >= self.max_size:
                                self.job_status_cache.popitem(last=False)

                            # Add the latest job status to the cache
                            self.job_status_cache[message_job_id] = (message_status, processing_duration)

                    try:
                        message.delete()
                    except Exception as e:
                        logger.warning("Unable to delete SQS message: ", e)

        except Exception as e:
            logger.error("Exception in ImageJobStatusMonitor.run() - Stopping", e)

    def stop(self) -> None:
        """Stop the monitoring thread."""
        self.running = False

    def check_job_status(self, job_id: str) -> tuple[Optional[str], Optional[int]]:
        """
        Check the status of a specific job from the cache.

        :param job_id: ID of the job to check
        :return: Tuple of (status, timestamp) if job exists, (None, None) otherwise
        """
        with self.job_status_cache_lock:
            return self.job_status_cache.get(job_id, (None, None))
