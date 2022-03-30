#!/usr/bin/env sh
# Builds and runs a development server image to be used locally.
# If you supply `-m` or `--mount`, it will mount your current code base onto the
# container so that you can test changes live.
set -e

source ./scripts/globals.sh

unset MOUNTLOCAL
export UWCA_CERT_PATH="${UWCA_CERT_PATH}"
export UWCA_CERT_NAME=${UWCA_CERT_NAME:-uwca}
APP_ENV_FILE=${APP_ENV_FILE:-husky_directory/settings/local.dotenv}
RUNENV="${RUNENV}"
USE_TEST_IDP=1


function print_help {
   cat <<EOF
   Use: run-development-server.sh [--debug --help]
   Options:
   -m, --mount     Mount your source code to avoid having to rebuild the image

   -c, --cert-path  The /path/to/your/ UWCA certificate (not required if
                    UWCA_CERT_PATH is set)

   -c, --cert-name  The name of your cert/key within --cert-path (not required if
                    UWCA_CERT_NAME is set)

   -e, --env       Passes the argument to the docker run command, e.g.,
                   `-e FOO=BAR` will make sure `FOO` is set to `BAR` on the
                   running instance.

   -i, --image     A complete image name you want to run; useful when testing something
                   that has already been pushed, e.g., gcr.io/uwit-mci-iam/uw-directory:2.0.1

   --idp           Use a real IdP. Not likely to work when running from your laptop!

   --compose       Use a docker-compose setup that includes redis and prometheus
                   integration. Without this, you must set '-e DEBUG_METRICS=true'
                   in order for metrics to export locally

   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}

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
      export UWCA_CERT_PATH=$1
      ;;
    # The name of the certificate (before the .crt/.key suffixes) located on the
    # declared path above.
    --cert-name)
      shift
      export UWCA_CERT_NAME=$1
      RUNENV="${RUNENV} -e UWCA_CERT_NAME=${UWCA_CERT_NAME}"
      ;;
    # You can provide environment variable arguments here to pass into Docker.
    -e|--env)
      shift
      RUNENV="${RUNENV} -e $1"
      ;;
    --image|-i)
      shift
      IMAGE=$1
      ;;
    --idp)
      USE_TEST_IDP=0
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    --debug|-g)
      set -x
      ;;
  esac
  shift
done

RUNENV="${RUNENV} -e USE_TEST_IDP=${USE_TEST_IDP}"

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
  echo "WARNING: No certificate is being mounted. You can still view the UI, but the search function will fail."
fi

./scripts/build-layers.sh
docker-compose -f docker/docker-compose.app.yaml up --build --exit-code-from app
