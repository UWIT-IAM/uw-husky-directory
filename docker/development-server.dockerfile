ARG BASE_VERSION=edge
FROM gcr.io/uwit-mci-iam/husky-directory-base:${BASE_VERSION} as poetry-base
ARG ENV_FILE=husky_directory/settings/base.dotenv
ARG HUSKY_DIRECTORY_VERSION=""
WORKDIR /scripts
# TODO: Move test stuff into its own layer
COPY scripts/validate-development-image.sh ./
COPY scripts/run-image-tests.sh ./
WORKDIR /tests
COPY tests ./
WORKDIR /app
COPY husky_directory/ ./husky_directory
# The next line allows the local network (e.g., your laptop) to communicate with the
# image, so that you can simply use: localhost:8000 in your browser.
EXPOSE 8000
ENV FLASK_PORT=8000 \
    FLASK_ENV=development \
    PYTHONPATH=/app:$PYTHONPATH \
    GUNICORN_LOG_LEVEL=DEBUG \
    DOTENV_FILE="$ENV_FILE" \
    HUSKY_DIRECTORY_VERSION=$HUSKY_DIRECTORY_VERSION \
    PROMETHEUS_MULTIPROC_DIR="/tmp/prometheus"

RUN mkdir -pv $PROMETHEUS_MULTIPROC_DIR && mkdir "/tmp/flask_session"
# 0.0.0.0 binding is necessary for the EXPOSE above to have any effect.
CMD poetry run gunicorn -b 0.0.0.0:${FLASK_PORT} \
    -c "/app/husky_directory/gunicorn.conf.py" \
    "husky_directory.app:create_app()"
