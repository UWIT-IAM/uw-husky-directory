# Builds and pushes the application image, and also pushes the base image.
# (The base image may not have been rebuilt.)

# Expected environment variables:
#
# BUILD_ID -- how the image will identify itself in its /health report
# BASE_VERSION -- "latest" if nothing else, otherwise some tag for the
# husky-directory-base image.
# APP_TAG -- The complete URI for the app image and tag.
# BASE_TAG -- The complete URI for the base image and tag.

set -e

docker build -f docker/development-server.dockerfile \
  --build-arg BUILD_ID=${BUILD_ID} \
  --build-arg BASE_VERSION=${BASE_VERSION} \
  -t ${APP_TAG} .
echo "Built and tagged ${TAG} with build id ${BUILD_ID}"
docker push ${BASE_TAG}
docker push ${APP_TAG}
echo pushed ${APP_TAG}
echo pushed ${BASE_TAG}
