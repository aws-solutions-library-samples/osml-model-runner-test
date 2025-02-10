
# Locust Load Tests for ModelRunner
This directory contains software necessary to test the OversightML ModelRunner service with Locust.

## Getting Started:
An example Conda environment for running these tests has been provided and can be setup using the following
commands:
```shell
conda env create -f environment-locust.yml
conda activate osml_model_runner_test
```

Once the Conda environment is running you can setup your AWS credentials into the shell and then start the
Locust test environment as shown.
```shell
export AWS_ACCOUNT="..."
locust -f ./bin/locust --class-picker \
  --aws-account ${AWS_ACCOUNT} \
  --test-imagery-location s3://osml-test-images-${AWS_ACCOUNT} \
  --test-results-location s3://mr-bucket-sink-${AWS_ACCOUNT}
```
The parameters shown above are the bare minimum parameters assuming a default installation of ModelRunner. Additional
command line options and the default values are shown below.

| Parameter Name	         | Default           |
|-------------------------|---------------------|
| --aws-region	           | “us-west-2”         |
| --aws-account	       | None                |
| --mr-input_queue	       | “ImageRequestQueue” |
| --mr-status-queue	   | “ImageStatusQueue”  |
| --test-imagery-location | None                |
| --test-results-location | None                |

This directory contains implementations of 2 Locust users that can be used to send different kinds of image processing
requests. The **PredefinedRequestUser** will cycle through requests defined in `bin/locust/sample-requests.json`.
Each request will have its template values filled in from the parameter values before it is sent. The
**RandomRequestsUser** will list all of the TIFF, and NITF files in the S3 bucket, query SageMaker to determine
what endpoints are available and then make requests from each image+endpoint pair chosen randomly.

There is also an implementation of a **PeriodicBurstLoadShape** which can be used to generate a load spike on a
regular basis. That LoadTestShape supports additional configuration options that can be set from the UI or
as command line arguments:

| Parameter Name	         | Default                                 |
|-------------------------|-------------------------------------------|
| --pbls-repeat-period    | 600                                       |
| --pbls-min-concurrency  | 5                                         |
| --pbls-peak-concurrency | 40                                        |
| --pbls-peak-std	       | None                                      |
| --pbls-peak-mean	       | None                                      |

## Implementation Details:

Class diagrams for the users and load shape are shown below. The plan is to continue expanding this baseline to
support additional user behaviors and load shapes as needed. The only thing outside of a typical Locust design
is the ModelRunner job monitoring thread that listens to SQS status messages and then keeps a data structure of
the most recent jobs. This is necessary because multiple independent users will submit jobs but ModelRunner only
sends status updates through a single channel.

```mermaid
classDiagram
    class User {
        <<Locust>>
    }

    class ModelRunnerUser {
        -ModelRunnerClient client
        -Environment environment
        +__init__(environment)
        -build_image_processing_request(...)
    }

    class PredefinedRequestUser {
        -List[Dict] requests
        -load_requests()
        +process_predefined_request()
    }

    class RandomRequestUser {
        -List[str] endpoint_names
        -List[str] image_urls
        -find_test_images()
        -find_test_endpoints()
        +process_random_image()
    }

    class ModelRunnerClient {
        -Environment environment
        -ImageJobStatusMonitor status_monitor
        +__init__(environment)
        +process_image(image_processing_request, timeout)
        +queue_image_processing_job(image_processing_request)
        +check_image_status(job_id)
        +wait_for_image_complete(job_id)
    }

    class ImageJobStatusMonitor {
        <<Singleton>>
        -Dict job_status_cache
        -Lock job_status_cache_lock
        -str status_queue_name
        -str status_queue_account
        -int max_size
        -bool running
        +__init__(queue_name, queue_account, max_size)
        +run()
        +stop()
        +get_job_status(job_id)
    }

    class ModelRunnerClientException {
        +str message
        +int status
        +Dict response_body
        +str job_id
        +__init__(message, status, response_body, job_id)
    }

    User <|-- ModelRunnerUser
    ModelRunnerUser <|-- PredefinedRequestUser
    ModelRunnerUser <|-- RandomRequestUser
    ModelRunnerUser *-- ModelRunnerClient
    ModelRunnerClient "*" --> "1" ImageJobStatusMonitor
    ModelRunnerClient ..> ModelRunnerClientException


```
```mermaid
classDiagram
    class LoadTestShape {
        <<Locust>>
        +tick() Tuple
    }

    class PeriodicBurstLoadShape {
        -int repeat_period
        -int min_concurrency
        -int peak_concurrency
        -float peak_std
        -float peak_mean
        +tick() Tuple
        -calculate_load_at_time(run_time) Tuple
    }

    LoadTestShape <|-- PeriodicBurstLoadShape
```
