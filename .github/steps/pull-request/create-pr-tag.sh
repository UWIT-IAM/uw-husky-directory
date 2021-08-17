#!/usr/bin/env bash

if ! source "${BUILD_SCRIPTS_DIR}/sources/github-actions.sh"
then
  echo "You must install common-build-scripts and set "
  echo "the BUILD_SCRIPTS_DIR environment variable."
  echo "Try: "
  echo "    export BUILD_SCRIPT_DIR=/tmp/build-scripts"
  echo "    ./.github/scripts/install-build-scripts.sh"
  echo "and then run this script again."
  echo
  exit 1
fi

function print_help {
   cat <<EOF
   Use: create-pr-tag.sh [--debug --help]
   Options:
   --source -s    The source image to tag for the pull request
   --help -h      Show this message and exit
   --debug -g     Show commands as they are executing
EOF
}

while (( $# ))
do
  case $1 in
    --source|-s)
      shift
      source_image="${1}"
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    --debug|-g)
      set -x
      ;;
    *)
      echo "Invalid Option: $1"
      print_help
      exit 1
      ;;
  esac
  shift
done

pr_number=$(jq --raw-output .pull_request.number "$GITHUB_EVENT_PATH")
test -n "pr_number" || exit 1
tag_name="pull-request-${pr_number}"
dest_image=gcr.io/uwit-mci-iam/husky-directory:${tag_name}
docker tag "${source_image}" ${dest_image}
docker push "${dest_image}"
set_ci_output image "${dest_image}"
