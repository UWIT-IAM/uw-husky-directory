# These first two commands will download the scripts and source files to `~/.common-build-scripts`
set -x
gh auth login --with-token $GITHUB_TOKEN
source <(curl -s https://raw.githubusercontent.com/UWIT-IAM/common-build-scripts/main/sources/github.sh)
get_tag_archive UWIT-IAM/common-build-scripts latest $BUILD_SCRIPTS_DIR
