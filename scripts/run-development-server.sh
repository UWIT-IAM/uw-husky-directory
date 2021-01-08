#!/usr/bin/env sh
# Builds and runs a development server image to be used locally.
# If you supply `-m` or `--mount`, it will mount your current code base onto the
# container so that you can test changes live.
set -e

unset MOUNTLOCAL
UWCA_CERT_PATH="${UWCA_CERT_PATH}"
UWCA_KEY_PATH="${UWCA_KEY_PATH}"
UWCA_CERT_NAME=${UWCA_CERT_NAME:-uwca}
APP_ENV_FILE=${APP_ENV_FILE:-husky_directory/settings/local.dotenv}
RUNENV="${RUNENV}"

while (( $# ))
do
  case $1 in
    # Run with `-m/--mount` to test changes live
    -m|--mount)
      MOUNTLOCAL="--mount type=bind,source="$(pwd)/husky_directory",target=/app/husky_directory"
      ;;
    # The path to your UWCA certificate on your filesystem
    # See docs/running-the-app.md
    -c|--cert-path)
      shift
      UWCA_CERT_PATH=$1
      ;;
    # The name of the certificate (before the .crt/.key suffixes) located on the
    # declared path above.
    --cert-name)
      shift
      UWCA_CERT_NAME=$1
      RUNENV="${RUNENV} -e UWCA_CERT_NAME=${UWCA_CERT_NAME}"
      ;;
    # You can provide environment variable arguments here to pass into Docker.
    -e)
      shift
      RUNENV="${RUNENV} -e $1"
      ;;
  esac
  shift
done

if test -n "${UWCA_CERT_PATH}"
then
  CERT_PREFIX="${UWCA_CERT_PATH}/${UWCA_CERT_NAME}"

  if ! test -e "${CERT_PREFIX}.crt"
  then
    ERROR=1
    echo "File ${CERT_PREFIX}.crt does not exist."
  fi
  if ! test -e "${CERT_PREFIX}.key"
  then
    ERROR=1
    echo "File ${CERT_PREFIX}.key does not exist"
  fi
  if test -n "${ERROR}"
  then
    echo \
    "    Cannot create a live instance because required certificate files cannot be
    mounted. You can use the \`--cert-name\` argument, provide the
    UWCA_CERT_NAME environment variable, or ensure
    the filenames in the provided path match ${UWCA_CERT_NAME}.crt and .key"
    exit 1
  fi
  MOUNTLOCAL="${MOUNTLOCAL} --mount type=bind,source=${UWCA_CERT_PATH},target=/app/certificates"
else
  echo "WARNING: No certificate is being mounted. Running the application may fail."
fi

docker build -f docker/development-server.dockerfile -t "uw-husky-directory-local" .
docker run ${RUNENV} -p 8000:8000 ${MOUNTLOCAL} -it uw-husky-directory-local
