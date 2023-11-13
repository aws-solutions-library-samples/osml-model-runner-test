#  Copyright 2023 Amazon.com, Inc. or its affiliates.
import os
from dataclasses import dataclass


@dataclass
class OSMLConfig:
    # topic names
    SNS_IMAGE_STATUS_TOPIC: str = os.getenv("SNS_IMAGE_STATUS_TOPIC", "ImageStatusTopic")
    SNS_REGION_STATUS_TOPIC: str = os.getenv("RegionStatusTopic")

    # queue names
    SQS_IMAGE_REQUEST_QUEUE: str = os.getenv("SQS_IMAGE_REQUEST_QUEUE", "ImageRequestQueue")
    SQS_REGION_REQUEST_QUEUE: str = os.getenv("SQS_REGION_REQUEST_QUEUE", "RegionRequestQueue")
    SQS_IMAGE_STATUS_QUEUE: str = os.getenv("SQS_IMAGE_STATUS_QUEUE", "ImageStatusQueue")
    SQS_REGION_STATUS_QUEUE: str = os.getenv("SQS_REGION_STATUS_QUEUE", "RegionStatusQueue")

    # table names
    DDB_JOB_STATUS_TABLE: str = os.getenv("DDB_JOB_STATUS_TABLE", "ImageProcessingJobStatus")
    DDB_FEATURES_TABLE: str = os.getenv("DDB_FEATURES_TABLE", "ImageProcessingFeatures")
    DDB_ENDPOINT_PROCESSING_TABLE: str = os.getenv("DDB_ENDPOINT_PROCESSING_TABLE", "EndpointProcessingStatistics")
    DDB_REGION_REQUEST_TABLE: str = os.getenv("DDB_REGION_REQUEST_TABLE", "RegionProcessingJobStatus")

    # sagemaker names
    SM_CENTERPOINT_MODEL: str = os.getenv("SM_CENTER_POINT_MODEL", "centerpoint")
    SM_FLOOD_MODEL: str = os.getenv("SM_FLOOD_MODEL", "flood")
    SM_AIRCRAFT_MODEL: str = os.getenv("SM_AIRCRAFT_MODEL", "aircraft")

    # HTTP model config
    HTTP_CENTERPOINT_MODEL_URL: str = os.getenv("HTTP_CENTER_POINT_MODEL_URL", None)
    HTTP_CENTERPOINT_MODEL_ELB_NAME: str = os.getenv("HTTP_CENTER_POINT_MODEL_ELB_NAME", "test-http-model-endpoint")
    HTTP_CENTERPOINT_MODEL_INFERENCE_PATH = os.getenv("HTTP_CENTERPOINT_MODEL_INFERENCE_PATH", "/invocations")

    # bucket name prefixes
    S3_RESULTS_BUCKET: str = os.getenv("S3_RESULTS_BUCKET")
    S3_RESULTS_BUCKET_PREFIX: str = os.getenv("S3_RESULTS_BUCKET_PREFIX", "test-results")
    S3_IMAGE_BUCKET_PREFIX: str = os.getenv("S3_IMAGE_BUCKET_PREFIX", "test-images")

    # stream name prefixes
    KINESIS_RESULTS_STREAM: str = os.getenv("KINESIS_RESULTS_STREAM")
    KINESIS_RESULTS_STREAM_PREFIX: str = os.getenv("KINESIS_RESULTS_STREAM_PREFIX", "test-stream")

    # deployment info
    ACCOUNT: str = os.environ.get("ACCOUNT")
    REGION: str = os.environ.get("REGION")

    # testing configuration
    TARGET_IMAGE: str = os.environ.get("TARGET_IMAGE")
    TARGET_MODEL: str = os.environ.get("TARGET_MODEL")
    TILE_FORMAT: str = os.environ.get("TILE_FORMAT", "GTIFF")
    TILE_COMPRESSION: str = os.environ.get("TILE_COMPRESSION", "NONE")
    TILE_SIZE: int = int(os.environ.get("TILE_SIZE", "512"))
    TILE_OVERLAP: int = int(os.environ.get("TILE_OVERLAP", "128"))
    FEATURE_SELECTION_OPTIONS: str = os.environ.get(
        "FEATURE_SELECTION_OPTIONS",
        '{"algorithm": "NMS", "iou_threshold":  0.75, "skip_box_threshold": 0.0001, "sigma": .1}',
    )


@dataclass
class OSMLLoadTestConfig:
    # sagemaker names/types
    SM_LOAD_TEST_MODEL: str = os.getenv("SM_LOAD_TEST_MODEL", "aircraft")

    # bucket names
    S3_LOAD_TEST_SOURCE_IMAGE_BUCKET: str = os.getenv("S3_SOURCE_IMAGE_BUCKET")
    S3_LOAD_TEST_RESULT_BUCKET: str = os.getenv("S3_LOAD_TEST_RESULT_BUCKET")

    # processing workflow
    PERIODIC_SLEEP_SECS: str = os.getenv("PERIODIC_SLEEP_SECS", "60")
    PROCESSING_WINDOW_MIN: str = os.getenv("PROCESSING_WINDOW_MIN", "1")
