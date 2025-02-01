function print_help {
   cat <<EOF
   Use: push-release-image.sh --version <semver> [--debug --help]
   Options:
   -v, --version   (Required)
                   The release version you want to dockerize and push to gar.

   --strict        Die on any errors
   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}

source ./scripts/globals.sh

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
./scripts/build-layers.sh -t ${version} --cache

source_image=${DOCKER_REPOSITORY}.development-server:${release_version}
dest_image=${DOCKER_REPOSITORY}:${release_version}

docker tag ${source_image} ${dest_image}


if [[ -z "${DRY_RUN}" ]]
then
  docker push ${dest_image}
else
  echo "Not pushing ${dest_image} in dry-run mode."
fi
