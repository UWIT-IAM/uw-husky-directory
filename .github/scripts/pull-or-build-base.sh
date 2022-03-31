# Attempts to pull the docker image; if it can't be pulled (likely
# because it doesn't exist), then build and tag it.
# Expected environment variables:
# BASE_TAG_NAME:
#     The complete URI to the base tag that we expect to find; the tag should be the
#     MD5 hash of the poetry.lock file that represents the state of all python
#     dependencies.
echo "Attempting to pull ${BASE_TAG_NAME}"
docker pull ${BASE_TAG_NAME} || PULL_FAILED=1

if [[ "${PULL_FAILED}" = "1" ]]
then
  echo "${BASE_TAG_NAME} pull failed; building it, instead."
  set -ex
  docker build -f docker/husky-directory-base.dockerfile \
    --build-arg FINGERPRINT -t ${BASE_TAG_NAME} .
  set +x
fi
