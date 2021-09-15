#!/usr/bin/env bash

# This script does some sanity checks on your code base, autoformats our code using 'black', and
# builds an image that will match the image used by our CI exactly. This will also invoke the
# dev validation tests (scripts/validate-development-image.sh) within the image, as a
# pretty good guarantee that your push will result in a successful post-push workflow.
#
# To run this, simply do:
#   ./scripts/pre-push.sh
#
REPO_HOST=gcr.io
REPO_PROJECT=uwit-mci-iam
APP_NAME=husky-directory
SRC_DIR=husky_directory
TST_DIR=tests
VIRTUAL_ENV=$(poetry env list --full-path 2>/dev/null | cut -f1 -d\ )
test -e ${VIRTUAL_ENV}/.envrc && source ${VIRTUAL_ENV}/.envrc
DOCKER_RUN_ARGS="${DOCKER_RUN_ARGS}"

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

   -v, --version   Tag an application version. (i.e., -v TAG_NAME).
                   Use with --test to build release candidates locally for
                   remote testing. The image will be stored locally
                   as ${REPO_HOST}/${REPO_PROJECT}/${APP_NAME}:TAG_NAME

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
    # succeed. Implies --no-commit
    --test)
      NO_EXIT_ON_FAIL=1
      NO_COMMIT=1
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

test -z "${NO_ENV_VARS}" && mkdir -p .pre_push

if test -n "$(git status --porcelain)"
then
  echo "🧹 Your git branch is dirty. Please resolve all outstanding changes before running this script."
  if test -z "${QUIET}"
  then
    echo "This script requires a clean git branch."
    git status
    echo "You can commit, stash, or reset changes you do not wish to include as part of the pre-push workflow."
  fi
  conditional_exit
fi

di_fingerprint=$(./scripts/get-snapshot-fingerprint.sh)
./scripts/update-dependency-image.sh

COMMIT_SHA=$(git log | head -n 1 | cut -f2 -d\ | cut -c 1-10)
COMMIT_TAG="commit-${COMMIT_SHA}"
conditional_echo "ℹ️ Commit tag is: ${COMMIT_TAG}"

IMAGE_NAME="$REPO_HOST/$REPO_PROJECT/$APP_NAME:$COMMIT_TAG"
if [[ -n "${GITHUB_REF}" ]]
then
  echo "::set-output name=image::$IMAGE_NAME"
fi

if ! black --check $SRC_DIR $TST_DIR > /dev/null
then
  conditional_echo "ℹ️ Blackening all code . . ."
  black $SRC_DIR $TST_DIR
  if test -z "${NO_COMMIT}"
  then
    conditional_echo "Amending your commit with blackened code."
    # Because the script won't run if the branch isn't clean, the only changes we should see are
    # those made by Black.
    git add -u
    git commit --amend --no-edit
  fi
else
  conditional_echo "🖤 Your code is already blackened. Good job! 🏴"
fi

conditional_echo "Building development server image"
BUILD_ARGS="${BUILD_ARGS} --build-arg BASE_VERSION=${di_fingerprint}"
docker build -f docker/development-server.dockerfile ${BUILD_ARGS} -t "${IMAGE_NAME}" .
conditional_echo "Tagged image ${IMAGE_NAME} with version: ${VERSION:-'<none provided>'}"
if [[ -n "${VERSION}" ]]
then
  version_tag="${REPO_HOST}/${REPO_PROJECT}/${APP_NAME}:${VERSION}"
  docker tag "${IMAGE_NAME}" "${version_tag}"
  conditional_echo "Tagged image ${version_tag}"
fi
if ! docker run -v "$(pwd)"/htmlcov:/app/htmlcov ${DOCKER_RUN_ARGS} "${IMAGE_NAME}" /scripts/validate-development-image.sh
then
  echo "☠️ Your commit should NOT be pushed."
  conditional_exit
fi

if test "$(git rev-parse --abbrev-ref HEAD)" == "main"
then
  echo "⚠️ Your commit looks OK, but it's on the wrong branch."
  conditional_echo "Run 'git switch -c feature-branch-name' to create a new branch, then run this script again."
fi

test -z "${NO_EXIT_ON_FAIL}" && echo "🛳 Your commit is good to go! 🌈"

if test -n "${NO_EXIT_ON_FAIL}"
then
  echo "👻 You ran this command in test mode so you could see the results of all validations."
  echo "Because of this, I can't validate your image. Therefore, I will fail now. Goodbye."
  exit 2
fi
