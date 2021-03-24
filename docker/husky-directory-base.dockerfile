ARG BASE_VERSION=latest
FROM gcr.io/uwit-mci-iam/uw-saml-poetry:${BASE_VERSION} as poetry-base
WORKDIR /app
COPY poetry.lock pyproject.toml ./
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN poetry install
