ARG BASE_VERSION=latest
ARG FINGERPRINT=""
FROM ghcr.io/uwit-iam/uw-saml-poetry:${BASE_VERSION} as poetry-base
WORKDIR /app
COPY poetry.lock pyproject.toml ./
ENV PATH="$POETRY_HOME/bin:$PATH" \
    UW_HUSKY_DIRECTORY_BASE_FINGERPRINT=${FINGERPRINT}
RUN poetry install
