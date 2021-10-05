ARG BASE_VERSION=latest
FROM ghcr.io/uwit-iam/uw-saml-poetry:${BASE_VERSION} as poetry-base
RUN apt-get update && apt-get -y install gcc
ARG FINGERPRINT=""
WORKDIR /app
COPY poetry.lock pyproject.toml ./
ENV PATH="$POETRY_HOME/bin:$PATH" \
    UW_HUSKY_DIRECTORY_BASE_FINGERPRINT=${FINGERPRINT}
RUN poetry install --no-root --no-interaction && apt-get -y remove gcc && apt-get -y autoremove
