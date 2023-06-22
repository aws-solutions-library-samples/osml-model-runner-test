# osml-model-runner-test

This package contains the integration tests for OSML application. This test can be executed via Hydra (pipeline) or from the local machine.

## Running Tests
You can run the hydra tests against your dev account by exporting the required parameters and using the pytest CLI by
using the demo utility ``bin/run_test.sh``.

```
export ACCOUNT="INSERT YOUR ACCOUNT"
export IMAGE_TYPE="INSERT YOUR IMAGE TYPE" # small, medium, large, or tile.<tif|ntf|jpeg|png>
export MODEL_TYPE="INSERT YOUR MODEL TYPE" # centerpoint, flood, or aircraft

./bin/run_test.sh ${IMAGE_TYPE} ${MODEL_TYPE} NITF JPEG us-west-2 $ACCOUNT_NUMBER
```

**Examples:**

```
./bin/run_test.sh small centerpoint NITF JPEG us-west-2 $ACCOUNT_NUMBER

./bin/run_test.sh medium flood NITF JPEG us-west-2 $ACCOUNT_NUMBER

./bin/run_test.sh large centerpoint NITF JPEG us-west-2 $ACCOUNT_NUMBER

./bin/run_test.sh tile.tif aircraft NITF JPEG us-west-2 $ACCOUNT_NUMBER
```

If you prefer, you can execute the python script:

```
python3 bin/process_image.py --image small --model centerpoint
```

To print out the usage for python script, execute:
```
python3 bin/process_image.py --help
```

## Running Tests in Docker
Arguments can be passed in to docker run in the same way that they are porvided to the shell script. For example, the container can be built and run as follows:

```
docker build . -t model-runner-hydra-test:latest
docker run -v ~/.aws:/root/.aws model-runner-hydra-test:latest small centerpoint NITF JPEG us-west-2 $ACCOUNT_NUMBER
```

Credentials from the users account are volume mounted into the container's root directory.

## Running LoadTest

You can run the load test against your dev account and be able to determine the cost and the performance.

**Examples:**
```
python3 bin/run_load_test.py --periodic_sleep 60 --processing_window 1
```

To print out the usage for this load test script, execute:

```
python3 bin/run_load_test.py --help
```
