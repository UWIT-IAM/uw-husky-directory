#!/usr/bin/env bash

set -e
source ./scripts/globals.sh

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
dest_image="${DOCKER_REPOSITORY}.app:${tag_name}"
docker tag "${source_image}" ${dest_image}
docker push "${dest_image}"
echo "::set-output name=image::${dest_image}"
echo "::notice::Pushed image https://${dest_image}"
