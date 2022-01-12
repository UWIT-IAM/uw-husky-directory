
./scripts/install-build-scripts.sh

export DOCKER_REPOSITORY="gcr.io/uwit-mci-iam/husky-directory"

function get_instance_version {
    local stage="$1"
    local url="https://directory.iam${stage}.s.uw.edu/health"
    local stage_status=$(curl -sk $url)
    local version=$(echo "$stage_status" | jq .version | sed 's|"||g')
    echo "$version"
}

function get_promotion_version {
  local target=$1
  case $target in
    dev)
      echo $(poetry version -s)
      ;;
    eval)
      echo $(get_instance_version dev)
      ;;
    prod)
      echo $(get_instance_version eval)
      ;;
  esac
}
