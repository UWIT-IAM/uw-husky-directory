ARG BASE_VERSION=latest
FROM gcr.io/uwit-mci-iam/husky-directory-base:${BASE_VERSION} as poetry-base
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
ARG BUILD_ID
ENV FLASK_PORT=8000 \
    FLASK_ENV=development \
    PYTHONPATH=/app:$PYTHONPATH \
    GUNICORN_LOG_LEVEL=DEBUG \
    BUILD_ID=${BUILD_ID} \
    PATH="$POETRY_HOME/bin:$PATH"

# 0.0.0.0 binding is necessary for the EXPOSE above to have any effect.
CMD poetry run gunicorn -b 0.0.0.0:${FLASK_PORT} \
    --log-level ${GUNICORN_LOG_LEVEL} \
    -c "/app/husky_directory/gunicorn.conf.py" \
    --reload \
    --capture-output \
    "husky_directory.app:create_app()"
