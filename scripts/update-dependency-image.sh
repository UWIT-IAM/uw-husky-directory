#!/usr/bin/env bash

./scripts/install-build-scripts.sh >/dev/null

function print_help {
   cat <<EOF
   Use: update-dependency-image.sh [OPTIONS]

   Options:
   -p, --push      Push the fingerprint after building, this is risk-free
                   and saves a lot of time in the future!
   --head          Include the head (i.e., 'latest') tag on the image
   --strict        Die on any errors
   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}

PUSH=

while (( $# ))
do
  case $1 in
    --help|-h)
      print_help
      exit 0
      ;;
    --debug|-g)
      set -x
      ;;
    --push|-p)
      PUSH=1
      ;;
    --head)
      TAG_LATEST=1
      ;;
    --debug|-g)
      set -x
      ;;
    --strict)
      set -e
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
image_repo=gcr.io/uwit-mci-iam/husky-directory-base
fingerprint=$(./scripts/get-snapshot-fingerprint.sh)
./.build-scripts/scripts/pull-or-build-image.sh \
  -i $image_repo:$fingerprint \
  -d docker/husky-directory-base.dockerfile

test -z "${TAG_LATEST}" || docker tag $image_repo:$fingerprint $image_repo:latest

if [[ -n "$PUSH" ]]
then
  docker push $image_repo:$fingerprint
  test -z "${TAG_LATEST}" || docker push $image_repo:latest
fi
