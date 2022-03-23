ARG uw_saml_poetry_version=latest
FROM ghcr.io/uwit-iam/uw-saml-poetry:${uw_saml_poetry_version} as base
WORKDIR /app

# gcc is required to install the Levenshtein library.
RUN apt-get update && apt-get -y install gcc curl jq

COPY poetry.lock pyproject.toml ./

ENV PATH="$POETRY_HOME/bin:$PATH"

RUN poetry install --no-dev --no-interaction \
    && apt-get -y remove gcc \
    && apt-get -y autoremove

FROM base as app
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
COPY ./scripts/validate-development-image.sh ./scripts/run-image-tests.sh ./
COPY ./tests /tests
COPY ./selenium-tests /selenium-tests
# Re-running install without the `--no-dev` arg to get the extra dependencies;
# the others won't need updating, so won't add extra time to the secondary run.
WORKDIR /app
RUN poetry install --no-interaction
# Make sure that unit tests are available at the root directory of the test-runner
WORKDIR /tests

# Make sure that selenium tests are
# available at the root directory of the selenium-runner
FROM test-runner AS selenium-runner
WORKDIR /selenium-tests

FROM app AS development-server
ENV FLASK_ENV=development
EXPOSE 8000
# 0.0.0.0 binding is necessary for the endpoint to be available externally.
CMD poetry run gunicorn -b 0.0.0.0:${FLASK_PORT} \
    -c "/app/husky_directory/gunicorn.conf.py" \
    "husky_directory.app:create_app()"
