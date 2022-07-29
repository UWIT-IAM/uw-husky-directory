
export DOCKER_REPOSITORY="gcr.io/uwit-mci-iam/husky-directory"

function get_instance_version {
    local stage="$1"
    local url="https://directory.iam${stage}.s.uw.edu/status"
    local stage_status=$(curl -sk $url)
    local version=$(echo "$stage_status" | jq .version | sed 's|"||g')
    echo "$version"
}

function get_instance_deployment_id {
    local stage="$1"
    local url="https://directory.iam${stage}.s.uw.edu/status"
    local stage_status=$(curl -sk $url)
    echo "$stage_status" | jq .deployment_id | sed 's|"||g'
}


function get_poetry_version {
  cat pyproject.toml | grep 'version =' | cut -f2 -d\" | head -n1
}


function get_promotion_version {
  local target=$1
  case $target in
    dev)
      echo $(get_poetry_version)
      ;;
    eval)
      echo $(get_instance_version dev)
      ;;
    prod)
      echo $(get_instance_version eval)
      ;;
  esac
}
