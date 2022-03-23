#!/usr/bin/env bash
# TODO: Replace with tox...
# This script does some validation checks on our code base,
# auto-formats our code using 'black', and
# builds an image that will match the image used by our CI exactly.
# Validation tests (scripts/validate-development-image.sh) are invoked from
# within the image itself pretty good guarantee that your push will result in a
# successful post-push workflow.
#
# To run this, simply do:
#   ./scripts/pre-push.sh --test  # Run any time!
#   ./scripts/pre-push.sh         # Run once your commit is ready
#   ./scripts/pre-push.sh --version 1.2.3  # Prepares a release image for docker push
SRC_DIR=husky_directory
TST_DIR=tests
CACHE_BUILD=1

DOCKER_RUN_ARGS="${DOCKER_RUN_ARGS}"

source ./scripts/globals.sh
source ./.build-scripts/sources/fingerprints.sh

function print_help {
   cat <<EOF
   Use: pre-push.sh [--version VERSION --test]

   Blackens all code, builds a docker image from the code, then
   runs all validations to ensure that the application is functioning
   appropriately.

   You must run this in "--test" mode unless your git branch is
   clean (i.e., ready to push). Running without "--test" amends your
   commit after blackening all code, so the utility protects you from amending
   a previous commit accidentally.

   You cannot opt out of blackening the code; our CI pipeline will do this for you
   even if you skip this step. It is recommended to always run this command
   before pushing to save the trouble of waiting for the workflow to fail.

   Options:

   --test          Run all validations even if some fail;
                   do not amend the HEAD commit to blacken code.
                   Use this until you're ready to actually push.

   -k, --skip-auto-format
                   Use this if you don't want to pre-blacken
                   your code. Note: this will not prevent a style
                   check from failing validations!

   -v, --version   Tag an application version. (i.e., -v TAG_NAME).
                   Use with --test to build release candidates locally for
                   remote testing. The image will be stored locally
                   as ${REPO_HOST}/${REPO_PROJECT}/${APP_NAME}:TAG_NAME

   --no-cache      Do not cache the resulting images in our docker repository.
                   When running with --test, this is always implied. You may want
                   to set this if you have a slow internet connection and don't want
                   to pre-push the fingerprinted images.

   --headless      Do not run docker in interactive mode; required when running
                   via remote automation (i.e., Github Actions)

   --quiet         Disables most output
   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}

while (( $# ))
do
  case $1 in
    # Hushes a lot of output!
    --quiet)
      QUIET=1
      ;;
    # This flag will keep executing the script even if some gateway steps fail
    # Be careful; this may have undefined behavior! If you use this flag, the script will
    # always fail (exit code 2); that way, this doesn't accidentally allow something automated to
    # succeed. Implies --no-commit and --no-cache
    --test)
      NO_EXIT_ON_FAIL=1
      NO_COMMIT=1
      CACHE_BUILD=
      ;;
    --no-cache)
      CACHE_BUILD=
      ;;
    --no-commit)
      NO_COMMIT=1
      ;;
    --skip-auto-format|-k)
      SKIP_AUTO_FORMAT=1
      ;;
    --headless)
      HEADLESS=1
      ;;
    --version|-v)
      shift
      VERSION="$1"
      BUILD_ARGS="$BUILD_ARGS --build-arg HUSKY_DIRECTORY_VERSION=$VERSION"
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    --debug|-g)
      DEBUG=1
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

test -n "${HEADLESS}" || DOCKER_RUN_ARGS+="-it "

function conditional_exit {
  test -z "${NO_EXIT_ON_FAIL}" && exit 1
}

function conditional_echo {
  test -z "${QUIET}" && echo $1
}

if test -n "$(git status --porcelain)"
then
  echo "Your git branch is dirty.
        If your commit is not ready, re-run with the '--test' flag."
  conditional_exit
fi

./scripts/build-app.sh --set-version ${VERSION} \
  $(test -z "${DEBUG}" || echo "-g") \
  $(test -z "${CACHE_BUILD}" || echo "--push")


autoformat_code() {
  if ! poetry run black --check $SRC_DIR $TST_DIR > /dev/null
  then
    poetry run black $SRC_DIR $TST_DIR
    if [[ -z "${NO_COMMIT}" ]]
    then
      conditional_echo "Amending your commit with blackened code."
      # Because the script won't run if the branch isn't clean,
      # the only changes we should see are those made by Black.
      git add -u
      git commit --amend --no-edit
    fi
  else
    conditional_echo "Your code is already blackened. Good job!"
  fi
}


test -n "${SKIP_AUTO_FORMAT}" || autoformat_code

APP_FINGERPRINT="$(./scripts/get-snapshot-fingerprint.sh -p agg)"
APP_IMAGE="${DOCKER_REPOSITORY}.app:${APP_FINGERPRINT}"
TEST_IMAGE="${DOCKER_REPOSITORY}.test-runner:${APP_FINGERPRINT}"

if [[ -n "${GITHUB_REF}" ]]
then
  echo "::set-output name=image::${APP_IMAGE}"
fi

docker build -f docker/husky-directory.dockerfile \
  --target test-runner \
  -t "${TEST_IMAGE}" .

if ! docker run \
  -v "$(pwd)"/htmlcov:/app/htmlcov -e USE_TEST_IDP=True \
  ${DOCKER_RUN_ARGS} "${TEST_IMAGE}" /scripts/validate-development-image.sh
then
  FAILURE=1
fi

if [[ -n "${FAILURE}" ]]
then
  echo "One or more validations failed. This commit is not ready!"
  echo "DO NOT PUSH."
  exit ${FAILURE}
elif [[ -n "${NO_EXIT_ON_FAIL}" ]]
then
  echo "All validations succeeded, but you ran this in test mode."
  echo "DO NOT PUSH."
  echo "(When you are ready, run without the '--test' flag!)"
else
  echo "🌈 Your commit is good to go! 🌈"
  echo "PUSH WHEN READY!"
fi
