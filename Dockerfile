# Set the base image to build from Internal Amazon Docker Image rather than DockerHub
# If a lot of request were made, CodeBuild will failed due to...
# "You have reached your pull rate limit. You may increase the limit by authenticating and upgrading"
ARG BASE_CONTAINER=public.ecr.aws/amazonlinux/amazonlinux:latest

FROM ${BASE_CONTAINER}

# Only override if you're using a mirror with a cert pulled in using cert-base as a build parameter
ARG BUILD_CERT=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem
ARG PIP_INSTALL_LOCATION=https://pypi.org/simple/

# Define required packages to install
ARG PACKAGES="wget"

# Give sudo permissions
USER root

# Configure, update, and refresh yum enviornment
RUN yum update -y && yum clean all && yum makecache

# Install all our dependancies
RUN yum install -y $PACKAGES

# Install miniconda
ARG MINICONDA_VERSION=Miniconda3-latest-Linux-x86_64
ARG MINICONDA_URL=https://repo.anaconda.com/miniconda/${MINICONDA_VERSION}.sh
RUN wget -c ${MINICONDA_URL} \
    && chmod +x ${MINICONDA_VERSION}.sh \
    && ./${MINICONDA_VERSION}.sh -b -f -p /usr/local

# Clean up installer file
RUN rm ${MINICONDA_VERSION}.sh

# Install python venv to the user profile
# This sets the python3 alias to be the miniconda managed python3.10 ENV
ARG PYTHON_VERSION=3.10
RUN conda install -q -y --prefix /usr/local python=${PYTHON_VERSION}

# Copy all our hydra tests
COPY . /home/
RUN chmod +x --recursive /home/
RUN chmod 777 --recursive /home/

# Hop in the home directory
WORKDIR /home

# Install the requirements using the conda provisioned python env
RUN python3 -m pip install \
    --index-url ${PIP_INSTALL_LOCATION} \
    --cert ${BUILD_CERT} \
    -r requirements.txt \
    codeguru_profiler_agent

# Install package module to the instance
RUN python3 setup.py install

# Clean up any dangling conda resources
RUN conda clean -afy

# Import the source directory to the generalized path
ENV PYTHONPATH="./src/"

# Set the entry point command to run unit tests
ENTRYPOINT ["bin/run_test.sh"]

# example build and run commands:
# docker build . -t model-runner-hydra-test:latest
# docker run -v ~/.aws:/root/.aws model-runner-hydra-test:latest small centerpoint NITF JPEG us-west-2 $ACCOUNT_NUMBER
