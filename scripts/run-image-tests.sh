#!/usr/bin/env bash
# Use this to run the tests inside a given docker image. (By default uses the
# uw-husky-directory-local)
set -e

source ./scripts/globals.sh

DOCKER_RUN_ARGS=

while (( $# ))
do
  case "$1" in
    # The name of the image to test
    -i|--image-name)
      shift
      IMAGE_NAME=$1
      ;;
    --headless)
      HEADLESS=1
      ;;
    # (Optional) arguments to pass to pytest; note that these will override
    # default arguments, including the testing directory.
    # Example, to run a single test, do:
    #   ./scripts/run-image-tests.sh -a '/tests/test_app.py::test_get_search'
    -a|--pytest-args)
      shift
      PYTEST_ARGS="$1"
      ;;
    # If provided, will build the image first; you'll often want this when testing
    # during development.
    -b|--build)
      BUILD_FIRST=1
      ;;
  esac
  shift
done

test -n "${HEADLESS}" || DOCKER_RUN_ARGS+="-it "
fingerprint=$(./scripts/get-snapshot-fingerprint.sh --profile aggregate)
DEFAULT_PYTEST_ARGS="/tests --cov=/app/husky_directory --cov-fail-under=95"
PYTEST_ARGS=${PYTEST_ARGS:-$DEFAULT_PYTEST_ARGS}
./scripts/build-app.sh
LAYER="test-runner"
IMAGE_NAME="${DOCKER_REPOSITORY}.${LAYER}:${fingerprint}"
docker build -f docker/husky-directory.dockerfile \
  --target "${LAYER}" \
  -t "${IMAGE_NAME}" .
set -x
docker run ${DOCKER_RUN_ARGS} ${IMAGE_NAME} pytest ${PYTEST_ARGS}
