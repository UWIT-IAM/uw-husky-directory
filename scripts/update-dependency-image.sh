#!/usr/bin/env bash


function print_help {
   cat <<EOF
   Use: update-dependency-image.sh [--debug --help]
   Options:
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

if [[ -n "$PUSH" ]]
then
  docker push $image_repo:$fingerprint
fi
