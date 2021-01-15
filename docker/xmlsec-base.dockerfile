FROM uwitiam/poetry:latest as uwit-iam-xmlsec-base
# These dependencies are large, so we set them as an environment variable to allow
# dependents to uninstall them easily if they wish, once all other installs have been
# completed: apt-get remove -y $XMLSEC_BUILD_DEPS
ENV XMLSEC_BUILD_DEPS="libxmlsec1-dev pkg-config build-essential"
RUN apt-get update && \
    apt-get install -y $XMLSEC_BUILD_DEPS && \
    apt-get install -y libxmlsec1-openssl && \
    pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -U xmlsec
