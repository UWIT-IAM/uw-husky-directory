# Builds and optionally caches all layers required for a running
# instance; does _not_ build test instances.

source ./scripts/globals.sh
source ./.build-scripts/sources/fingerprints.sh


function print_help {
   cat <<EOF
   Builds and optionally pushes docker layers that comprise
   the Husky Directory app. The layers will be named using the
   following format:
      ${DOCKER_REPOSITORY}.<layer>:<layer-fingerprint>

   A layer's fingerprint is determined by the layer dependencies,
   built directives, and contents. This fingerprint is deterministic (SHA256 digest)
   so layers can be cached safely at any time (using the '--push' flag).

   Use: ./scripts/build-images.sh [OPTIONS]

   OPTIONS:
   -p, --push           Push each layer after building
   -f, --force-rebuild  Rebuild layers even if the fingerprints match existing tags
   -v, --set-version    Sets the HUSKY_DIRECTORY_VERSION environment variable for the
                        resulting image
   -t, --tag-version    Also tags an image with this version, if set. Only required
                        if you need to deploy the result.
   -h, --help           Show this message and exit
   -g, --debug          Show commands as they are executing
EOF
}

PUSH_AFTER_BUILD=
FORCE_REBUILD=
SET_VERSION=
DOCKERFILE="docker/husky-directory.dockerfile"
DEPENDENCY_FINGERPRINT=$(./scripts/get-snapshot-fingerprint.sh -p dep)
AGG_FINGERPRINT=$(./scripts/get-snapshot-fingerprint.sh -p agg)
LAYERS=(
  base
  app
  development-server
)
build_args=""

create_layer() {
  local layer=$1
  local layer_tag=$2
  # If the layer is already present on the system or if the
  # layer tag can be pulled remotely, skip this layer unlss
  # --force-rebuild was used.
  if [[ -n "$(docker images -q ${layer_tag})" ]] || docker pull ${layer_tag} 2>/dev/null
  then
    test -n "${FORCE_REBUILD}" || return
  fi

  docker build -f "$DOCKERFILE" \
    --build-arg HUSKY_DIRECTORY_VERSION="${SET_VERSION}" \
    --target "${layer}" \
    -t "${layer_tag}" . || return 1
  if [[ -n "${TAG_VERSION}" ]]
  then
    local version_tag="${DOCKER_REPOSITORY}.${layer}:${SET_VERSION}"
    docker tag "${layer_tag}" "${version_tag}"
  fi
}

# Tracks the most recently built tag, to be used as an output from
# the build_layer function
built_layer_tag=

build_layer() {
  built_layer_tag=
  layer=$1
  local layer_tag="${DOCKER_REPOSITORY}.${layer}"
  # The base layer has a different fingerprint structure
  # than the others, so we route this to a different function
  if [[ "${layer}" == "base" ]]
  then
    layer_tag+=":${DEPENDENCY_FINGERPRINT}"
  else
    layer_tag+=":${AGG_FINGERPRINT}"
  fi
  create_layer "${layer}" "${layer_tag}"
  built_layer_tag="${layer_tag}"
}

while (( $# ))
do
  case $1 in
    --push)
      PUSH_AFTER_BUILD=1
      ;;
    --force-rebuild|-f)
      FORCE_REBUILD=1
      ;;
    --set-version|-v)
      shift
      SET_VERSION="$1"
      ;;
    --tag-version|-t)
      TAG_VERSION=1
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    --debug|-g)
      DEBUG=1
      ;;
    *)
      echo "Invalid Option: $1"
      print_help
      exit 1
      ;;
  esac
  shift
done

test -z "${DEBUG}" || set -x
export DEBUG="${DEBUG}"
for layer in "${LAYERS[@]}"
do
  build_layer "${layer}"
  if [[ -n "${PUSH_AFTER_BUILD}" ]]
  then
    docker push "${built_layer_tag}"
  fi
done
