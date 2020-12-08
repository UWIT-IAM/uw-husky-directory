#!/usr/bin/env sh
# Builds and runs a development server image to be used locally.
# If you supply `-m` or `--mount`, it will mount your current code base onto the
# container so that you can test changes live.
set -ex

unset MOUNTLOCAL

for arg in $@
do
  # Run with `-m/--mount` to test changes live
  case $arg in
    -m|--mount)
      MOUNTLOCAL="--mount type=bind,source="$(pwd)/husky_directory",target=/app/husky_directory"
      ;;
  esac
done

docker build -f docker/development-server -t "uw-husky-directory-local" .
docker run -p 8000:8000 ${MOUNTLOCAL} -it uw-husky-directory-local
