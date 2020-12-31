FROM uwitiam/poetry:latest as poetry-base
WORKDIR $PYSETUP_PATH
COPY poetry.lock pyproject.toml ./
RUN poetry install

# `development` image is used during development / testing
FROM poetry-base AS copy-tests
# copy in our built poetry + venv
COPY --from=0 $POETRY_HOME $POETRY_HOME
COPY --from=0 $PYSETUP_PATH $PYSETUP_PATH
# Then copy the tests
WORKDIR /tests
COPY tests ./

FROM copy-tests AS copy-scripts
WORKDIR /scripts
COPY scripts/validate-development-image.sh ./
COPY scripts/run-image-tests.sh ./

FROM copy-scripts AS app
WORKDIR /app
COPY husky_directory/ ./husky_directory
# The next line allows the local network (e.g., your laptop) to communicate with the
# image, so that you can simply use: localhost:8000 in your browser.
EXPOSE 8000
ENV FLASK_PORT=8000 \
    FLASK_ENV=development \
    PYTHONPATH=/app:$PYTHONPATH \
    GUNICORN_LOG_LEVEL=DEBUG

# 0.0.0.0 binding is necessary for the EXPOSE above to have any effect.
CMD gunicorn -b 0.0.0.0:${FLASK_PORT} \
    --log-level ${GUNICORN_LOG_LEVEL} \
    -c "/app/husky_directory/gunicorn.conf.py" \
    --reload \
    --capture-output \
    "husky_directory.app:create_app()"
