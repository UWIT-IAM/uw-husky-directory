#!/usr/bin/env sh

# This script does some sanity checks on your code base, autoformats our code using 'black', and
# builds an image that will match the image used by our CI exactly. This will also invoke the
# dev validation tests (scripts/validate-development-image.sh) within the image, as a
# pretty good guarantee that your push will result in a successful post-push workflow.
#
# To run this, simply do:
#   ./scripts/pre-push.sh
#
# If successful, this script will create (or replace) the file .pre_push/last in your current directory.
# This contains some helpful environment variables for referencing your commit and push.
# You can import those at any time using: 'source .pre_push/last'
#
# The variables themselves are used in some helpful output, so that you can copy and paste the output directly to
# execute other steps.
#
# Following is a list of environment variables exported by .pre_push/last:
#   - COMMIT_SHA: A string containing the first 10 characters of the commit SHA for when this script last succeeded.
#                 This can be a useful way to construct meaningful commits. See docs/commits.md.
#                 Example value: ab1c234de5
#                 How to use it:  git reset ${COMMIT_SHA}
#
#   - COMMIT_TAG: A string that contains only the tag name created from your commit message. Useful for comparing to
#                 to see when your last commit image is from (i.e., at which commit you last ran this script).
#                 Use this if you want to search for the tag somewhere.
#                 Example value: commit-ab1c234de5
#
#   - COMMIT_IMAGE: A string of the fully qualified image name for this commit. You can push this somewhere if you like,
#                   or use it to tag another image.
#                   Example value: uwitiam/husky-directory:commit-ab1c234de5
#                   How to use it: docker run -it "${COMMIT_IMAGE}"
#
#   - PERSONAL_IMAGE: A string similar to COMMIT_IMAGE, but with a tag including your current environment username.
#                          Example value: uwitiam/husky-directory:personal-foobar
#                          If you wish for the base to use a different personal name, export or set the
#                          PERSONAL_IMAGE_SUFFIX environment variable. (e.g., PERSONAL_IMAGE_SUFFIX=justfoo)
#                          Use this to maintain an image for some personal use case, or deployment environment.
#                          How to use it: docker tag "${COMMIT_IMAGE}" "${PERSONAL_IMAGE}" \
#                                             && docker push "${PERSONAL_IMAGE}"
#
# There are some options available for running this script; you will see them documented below.

DOCKER_ORG=uwitiam
APP_NAME=husky-directory
SRC_DIR=husky_directory
TST_DIR=tests
VIRTUAL_ENV=$(poetry env list --full-path 2>/dev/null | cut -f1 -d\ )
test -e ${VIRTUAL_ENV}/.envrc && source ${VIRTUAL_ENV}/.envrc
PERSONAL_IMAGE_SUFFIX=${PERSONAL_IMAGE_SUFFIX:-$USER}
CACHE_PATH=./.pre_push

for item in "$@"
do
  case $item in
    # This will skip some helpful hints in the output. Use this if you want less output and think you know what
    # you are doing.
    "--pro")
      QUIET=1
      ;;
    # This flag will keep executing the script even if some gateway steps fail
    # Be careful; this may have undefined behavior! If you use this flag, the script will
    # always fail (exit code 2); that way, this doesn't accidentally allow something automated to
    # succeed. Implies --no-commit
    "--test")
      NO_EXIT_ON_FAIL=1
      NO_COMMIT=1
      ;;
    # This will prevent creating/overwriting artifact # environment variables.
    # Only use this if you really don't want the convenience.
    "--incognito")
      NO_ENV_VARS=1
      ;;
    # This will prevent some auto-commit features, such as for blackened code or appending the pre-push validation.
    # Not recommended, as it could cause CI to fail if you push code that needed the automatic updates.
    "--no-commit")
      NO_COMMIT=1
      ;;
  esac
done

function conditional_exit() {
  test -z "${NO_EXIT_ON_FAIL}" && exit 1
}

function conditional_echo() {
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

COMMIT_SHA=$(git log | head -n 1 | cut -f2 -d\ | cut -c 1-10)
COMMIT_TAG="commit-${COMMIT_SHA}"
conditional_echo "ℹ️ Commit tag is: ${COMMIT_TAG}"

IMAGE_NAME="$DOCKER_ORG/$APP_NAME:$COMMIT_TAG"
PERSONAL_IMAGE="$DOCKER_ORG/$APP_NAME:personal-$PERSONAL_IMAGE_SUFFIX"

if ! black --check $SRC_DIR $TST_DIR > /dev/null
then
  conditional_echo "ℹ️ Blackening all code . . ."
  black $SRC_DIR $TST_DIR
  conditional_echo "Amending your commit with blackened code:"
  # Because the script won't run if the branch isn't clean, the only changes we should see are
  # those made by Black.
  git add -u
  git commit --amend --no-edit
else
  conditional_echo "🖤 Your code is already blackened. Good job! 🏴"
fi

conditional_echo "Building development server image"
docker build -f docker/development-server.dockerfile -t "${IMAGE_NAME}" .
conditional_echo "Tagged image ${IMAGE_NAME}"
if ! docker run -v "$(pwd)"/htmlcov:/app/htmlcov -it "${IMAGE_NAME}" /scripts/validate-development-image.sh
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

if test -z "${NO_ENV_VARS}"
then
  artifact=${CACHE_PATH}/${COMMIT_SHA}
  conditional_echo "ℹ️ Creating ${artifact}; you can source this to re-populate environment variables later."
  echo "#!/usr/bin/env sh" > $artifact
  echo "export COMMIT_SHA=${COMMIT_SHA}" >> $artifact
  echo "export COMMIT_IMAGE=${IMAGE_NAME}" >> $artifact
  echo "export PERSONAL_IMAGE=${PERSONAL_IMAGE}" >> $artifact
  echo "export COMMIT_TAG=${COMMIT_TAG}" >> $artifact
  conditional_echo "Symlinking ${artifact} to .pre_push/last"
  pushd $CACHE_PATH
    ln -s -f ${COMMIT_SHA} last
  popd
fi


if test -z "${QUIET}"
then
  echo ""
  echo "OPTIONAL NEXT STEPS: "
  echo "  - Populate environment variables from this run: source .pre_push/last"
  echo "  - Tag the image for a personal instance: docker tag \${COMMIT_IMAGE} \${PERSONAL_IMAGE}"
  echo "    then push the personal image for live testing: docker push \${PERSONAL_IMAGE}"
  echo "    then visit https://directory-${PERSONAL_IMAGE_SUFFIX}.iamdev.s.uw.edu"
  echo "  - Push to remote: git push "
  echo "    then create a code review: https://github.com/UWIT-IAM/uw-husky-directory/compare"
  echo ""
  if test -n "${NO_ENV_VARS}"
  then
    echo "❗️You ran this with --no-env, which means the environment variables exemplified above are NOT set."
    conditional_echo "If you want to make use of them, simply run this script again, without the '--no-env' flag."
  fi
fi

if test -n "${NO_EXIT_ON_FAIL}"
then
  echo "👻 You ran this command in test mode so you could see the results of all validations."
  echo "Because of this, I can't validate your image. Therefore, I will fail now. Goodbye."
  exit 2
fi
