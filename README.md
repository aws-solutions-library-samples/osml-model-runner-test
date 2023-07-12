# OSML Model Runner Test

This package contains the integration tests for OSML application

### Table of Contents
* [Getting Started](#getting-started)
    * [Prerequisites](#prerequisites)
    * [Installation Guide](#installation-guide)
    * [Documentation](#documentation)
    * [Build and Local Testing](#build-and-local-testing)
    * [Running Tests in Docker](#running-tests-in-docker)
    * [Running LoadTest](#running-loadtest)
* [Support & Feedback](#support--feedback)
* [Security](#security)
* [License](#license)


## Getting Started
### Prerequisites

First, ensure you have installed the following tools locally

1. [aws cli](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
2. [docker](https://nodejs.org/en)
3. [tox](https://tox.wiki/en/latest/installation.html)

### Installation Guide

1. Clone `osml-model-runner-test` package into your desktop

```sh
git clone https://github.com/aws-solutions-library-samples/osml-model-runner-test.git
```

2. Run `tox` to create a virtual environment

```sh
cd osml-model-runner-test
tox
```



### Documentation

You can find documentation for this library in the `./doc` directory. Sphinx is used to construct a searchable HTML
version of the API documents.

```shell
tox -e docs
```


## Linting/Formatting

This package uses a number of tools to enforce formatting, linting, and general best practices:

- [black](https://github.com/psf/black)
- [isort](https://github.com/PyCQA/isort) for formatting with a max line length of 100
- [mypy](https://github.com/pre-commit/mirrors-mypy) to enforce static type checking
- [flake8](https://github.com/PyCQA/flake8) to check pep8 compliance and logical errors in code
- [autopep](https://github.com/pre-commit/mirrors-autopep8) to check pep8 compliance and logical errors in code
- [eslint](https://github.com/pre-commit/mirrors-eslint) to check pep8 compliance and logical errors in code
- [prettier](https://github.com/pre-commit/mirrors-prettier) to check pep8 compliance and logical errors in code
- [pre-commit](https://github.com/pre-commit/pre-commit-hooks) to install and control linters in githooks

```bash
python3 -m pip install pre-commit
pre-commit install
```

Additionally, you can perform linting on all the files in the package by running:
```bash
pre-commit run --all-files --show-diff-on-failure
```

### Build and Local Testing

You can run the hydra tests against your dev account by exporting the required parameters and using the pytest CLI by
using the demo utility ``bin/run_test.sh``. Do not forget to load up your AWS credentials into your terminal, please follow this [guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html) on how to load your aws credentials.


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

### Running Tests in Docker
Arguments can be passed in to docker run in the same way that they are porvided to the shell script. For example, the container can be built and run as follows:

```
docker build . -t model-runner-hydra-test:latest
docker run -v ~/.aws:/root/.aws model-runner-hydra-test:latest small centerpoint NITF JPEG us-west-2 $ACCOUNT_NUMBER
```

Credentials from the users account are volume mounted into the container's root directory.

### Running LoadTest

You can run the load test against your dev account and be able to determine the cost and the performance. **Please advise** it can potentially rack up your AWS bills!

**Examples:**
```
python3 bin/run_load_test.py --periodic_sleep 60 --processing_window 1
```

To print out the usage for this load test script, execute:

```
python3 bin/run_load_test.py --help
```

## Support & Feedback

To post feedback, submit feature ideas, or report bugs, please use the [Issues](https://github.com/aws-solutions-library-samples/osml-model-runner-test/issues) section of this GitHub repo.

If you are interested in contributing to OversightML Model Runner, see the [CONTRIBUTING](CONTRIBUTING.md) guide.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

MIT No Attribution Licensed. See [LICENSE](LICENSE).
