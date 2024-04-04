# OSML Model Runner Test

This package contains the integration tests for OSML application

### Table of Contents
* [Getting Started](#getting-started)
    * [Prerequisites](#prerequisites)
    * [Installation Guide](#installation-guide)
    * [Documentation](#documentation)
    * [Build and Local Testing](#build-and-local-testing)
    * [Running LoadTest](#running-loadtest)
* [Support & Feedback](#support--feedback)
* [Security](#security)
* [License](#license)


## Getting Started
### Prerequisites

First, ensure you have installed the following tools locally

1. [aws cli](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
2. [tox](https://tox.wiki/en/latest/installation.html)

### Installation Guide

1. Clone `osml-model-runner-test` package into your desktop

```sh
git clone https://github.com/aws-solutions-library-samples/osml-model-runner-test.git
```

1. Run `tox` to create a virtual environment

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

### Local Testing


####  Credentials

Credentials from the user's account are volume mounted into the container's root directory.

**Processing an image:**

You can run the integration tests against your dev account by exporting the required parameters and using the pytest CLI by
using the python script ``bin/process_image.py``. Remember to load up your AWS credentials into your terminal, please follow this [guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html) on how to load your aws credentials.


```
python bin/process_image.py --image <image type> --model <model type>
```

**Examples:**

```
python3 bin/process_image.py --image small --model centerpoint

python3 bin/process_image.py --image meta --model centerpoint

python3 bin/process_image.py --image large --model flood

python3 bin/process_image.py --image tile_tif --model aircraft
```

To print out the usage for python script, execute:
```
python3 bin/process_image.py --help
```

To execute the integration test, exclude `--skip_integ` from the command line interface. It is essential that the images and models listed in the table below are aligned accurately for the test to succeed. Conversely, by adding `--skip_integ` to the CLI, all comparison checks will be bypassed, rendering the table irrelevant for testing purposes.

| image                       | model       |
|-----------------------------|-------------|
| small                       | centerpoint |
| meta                        | centerpoint |
| sicd_capella_chip_ntf       | centerpoint |
| sicd_umbra_chip_ntf         | centerpoint |
| sicd_interferometric_hh_ntf | centerpoint |
| wbid                        | centerpoint |
| large                       | flood       |
| tile_tif                    | aircraft    |
| tile_ntf                    | aircraft    |
| tile_jpeg                   | aircraft    |
| tile_png                    | aircraft    |

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

If you are interested in contributing to OversightML Model Runner, see the [CONTRIBUTING](https://github.com/aws-solutions-library-samples/osml-model-runner-test/tree/main/CONTRIBUTING.md) guide.

## Security

See [CONTRIBUTING](https://github.com/aws-solutions-library-samples/osml-model-runner-test/tree/main/CONTRIBUTING.md) for more information.

## License

MIT No Attribution Licensed. See [LICENSE](https://github.com/aws-solutions-library-samples/osml-model-runner-test/tree/main/LICENSE).
