#  Copyright 2023 Amazon.com, Inc. or its affiliates.
import logging

import boto3

from .osml_config import OSMLConfig

logging.getLogger("botocore").setLevel(logging.CRITICAL)


def get_session_credentials() -> boto3.session.Session:
    """
    Get new session (this will prevent out-dated credentials)

    :return: boto3.session.Session = session
    """
    return boto3.session.Session(region_name=OSMLConfig.REGION)


def sqs_client() -> boto3.resource:
    """
    Get resources from the default SQS session

    :return: boto3.resource = sqs resources
    """
    session = get_session_credentials()
    return session.resource("sqs", region_name=OSMLConfig.REGION)


def ddb_client() -> boto3.resource:
    """
    Get resources from the default DDB session

    :return: boto3.resource = ddb resources
    """
    session = get_session_credentials()
    return session.resource("dynamodb", region_name=OSMLConfig.REGION)


def s3_client() -> boto3.client:
    """
    Get service client by name using the default S3 session

    :return: boto3.client = s3 resources
    """
    session = get_session_credentials()
    return session.client("s3", region_name=OSMLConfig.REGION)


def kinesis_client() -> boto3.client:
    """
    Get service client by name using the default Kinesis session

    :return: boto3.client = kinesis resources
    """
    session = get_session_credentials()
    return session.client("kinesis", region_name=OSMLConfig.REGION)


def sm_client() -> boto3.client:
    """
    Get resources from the default SageMaker session

    :return: boto3.resource = SM resources
    """
    session = get_session_credentials()
    return session.client("sagemaker", region_name=OSMLConfig.REGION)


def cw_client() -> boto3.client:
    """
    Get resources from the default CloudWatch session

    :return: boto3.resource = CW resources
    """
    session = get_session_credentials()
    return session.client("cloudwatch", region_name=OSMLConfig.REGION)


def elb_client() -> boto3.client:
    """
    Get resources from the default ElasticLoadBalancing session

    :return: boto3.client = ELB client
    """
    session = get_session_credentials()
    return session.client("elbv2", region_name=OSMLConfig.REGION)
