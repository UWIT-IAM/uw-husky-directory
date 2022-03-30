function print_help {
   cat <<EOF
   Use: build-layers.sh [--debug --help]
   Options:
   -v,
   -f, --force     Execute docker builds even if no changes are detected
   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}

./scripts/install-build-scripts.sh
source ./.build-scripts/sources/docker-layers.sh # || exit 1
source ./scripts/globals.sh
export DOCKERFILE=Dockerfile
export DOCKER_REPOSITORY=gcr.io/uwit-mci-iam/husky-directory

function parse_args {
  while (( $# ))
  do
    case $1 in
      --help|-h)
        print_help
        exit 0
        ;;
      --debug|-g)
        DEBUG=1
        ;;
      -f|--force)
        FORCE_REBUILD=1
        ;;
      --cache)
        CACHE_LAYERS=1
        ;;
      -t|--add-tag)
        shift
        ADDITIONAL_TAGS+="${1} "  # whitespace intentional
        ;;
      *)
        echo "Invalid Option: $1"
        print_help
        return 1
        ;;
    esac
    shift
  done

test -z "${DEBUG}" || set -x
export DEBUG="${DEBUG}"
}

function get_layer_tag {
  local layer_name="$1"
  local tag="$2"
  echo "${DOCKER_REPOSITORY}.${layer_name}:${tag}"
}

function get_layer_fingerprint {
  local layer_name="${1}"
  case "${layer_name}" in
    base)
      fp_target=dependencies
      ;;
    test-runner|selenium-runner)
      fp_target=tests
      ;;
    *)
      fp_target=source
      ;;
  esac
  poetry run python -m fingerprinter.cli -t "${fp_target}" -f fingerprints.yaml
}

function build_layer {
  local layer_name=$1
  local build_args=
  case "${layer_name}" in
    app)
      build_args="--build-arg HUSKY_DIRECTORY_VERSION=$(get_poetry_version) "
      ;;
  esac

  local fingerprint=$(get_layer_fingerprint ${layer_name})
  echo "Reconciling layer: ${layer}:${fingerprint}"
  get_or_create_layer "${layer_name}" "${fingerprint}" \
    $(test -z "${FORCE_REBUILD}" || echo "--force") ${build_args} || return 1
  tag_and_push_image $(get_layer_tag ${layer_name} ${fingerprint})
}

function tag_and_push_image {
  local source_image_name="${1}"
  test -z "${CACHE_LAYERS}" || docker push ${source_image_name}
  local source_image_base_name=$(echo ${source_image_name} | cut -f1 -d:)
  tags="${ADDITIONAL_TAGS}"
  for tag in ${ADDITIONAL_TAGS}
  do
    local dest_image_name="${source_image_base_name}:${tag}"
    echo "Tagging ${dest_image_name}"
    docker tag ${source_image_name} ${dest_image_name}
    test -z "${CACHE_LAYERS}" || docker push ${dest_image_name}
  done
}

function build_layers {
  for layer in $@
  do
    build_layer "${layer}" || return 1
  done
}

parse_args "$@" || exit $?
poetry install
layers="$(grep "^FROM" ${DOCKERFILE} | cut -f4 -d' ')"
build_layers ${layers}