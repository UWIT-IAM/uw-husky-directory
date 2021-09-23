function print_help {
   cat <<EOF
   Use: push-release-image.sh --version <semver> [--debug --help]
   Options:
   -v, --version   (Required)
                   The release version you want to dockerize and push to gcr.

   --strict        Die on any errors
   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}

while (( $# ))
do
  case $1 in
    --version|-v)
      shift
      release_version="$1"
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    --debug|-g)
      DEBUG=1
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

test -n "${release_version}" || exit 1
test "${GITHUB_REF}" == "refs/heads/main" || DRY_RUN=1

./scripts/update-dependency-image.sh --strict --head \
  $(test -n "${DRY_RUN}" || echo '--push') \
  $(test -z "${DEBUG}" || echo "--debug" )

./scripts/pre-push.sh \
  --version $release_version \
  --headless --skip-auto-format \
  $(test -z "${DEBUG}" || echo "--debug")

if [[ -z "${DRY_RUN}" ]]
then
  docker push gcr.io/uwit-mci-iam/husky-directory:$version
else
  echo "Not pushing $release_image in dry-run mode."
fi
