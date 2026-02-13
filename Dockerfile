# ARG uw_saml_poetry_version=latest
# FROM ghcr.io/uwit-iam/uw-saml-poetry:${uw_saml_poetry_version} AS base
# WORKDIR /app

# # gcc is required to install the Levenshtein library.
# RUN apt-get update && apt-get -y install gcc curl jq git

# Use the python-base image (no need for uw-saml-poetry anymore)
ARG APP_IMAGE=app
# Use the python-base image
FROM us-docker.pkg.dev/uwit-mci-iam/containers/base-python-3.12 AS app-base

# Install system dependencies necessary for the app, previously installed by uw-saml-poetry image:
# https://github.com/UWIT-IAM/docker-library/blob/main/images/uw-saml-poetry/bootstrap-xmlsec-env.sh
RUN apt-get update && apt-get install -y \
    libxmlsec1-dev \
    build-essential \
    pkg-config \
    libxmlsec1-openssl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY poetry.lock pyproject.toml ./

RUN poetry install --no-interaction --without dev \
    && apt-get -y remove gcc \
    && apt-get -y autoremove

FROM app-base AS app
WORKDIR /app
ARG HUSKY_DIRECTORY_VERSION
COPY ./husky_directory ./husky_directory/
ENV PYTHONPATH="/app:${PYTHONPATH}" \
    DOTENV_FILE="/app/husky_directory/settings/base.dotenv" \
    PROMETHEUS_MULTIPROC_DIR="/tmp/prometheus" \
    FLASK_PORT=8000 \
    HUSKY_DIRECTORY_VERSION=${HUSKY_DIRECTORY_VERSION} \
    GUNICORN_LOG_LEVEL=DEBUG

RUN mkdir -pv $PROMETHEUS_MULTIPROC_DIR && mkdir "/tmp/flask_session"

FROM app AS test-runner
WORKDIR /scripts
COPY ./tests /tests
COPY ./selenium-tests /selenium-tests
# Re-running install without the `--without dev` arg to get the extra dependencies;
# the others won't need updating, so won't add extra time to the secondary run.
WORKDIR /app
RUN poetry install --no-interaction
# Make sure that unit tests are available at the root directory of the test-runner
WORKDIR /tests
CMD pytest \
        --cov husky_directory \
        --cov-fail-under 99 \
        --cov-report html \
        --cov-report term-missing \
        ${pytest_args}

# Make sure that selenium tests are
# available at the root directory of the selenium-runner
FROM test-runner AS selenium-runner
WORKDIR /selenium-tests

FROM app AS development-server
ENV FLASK_ENV=development
EXPOSE 8000
# 0.0.0.0 binding is necessary for the endpoint to be available externally.
CMD gunicorn -b 0.0.0.0:${FLASK_PORT} \
    -c "/app/husky_directory/gunicorn.conf.py" \
    "husky_directory.app:create_app()"
