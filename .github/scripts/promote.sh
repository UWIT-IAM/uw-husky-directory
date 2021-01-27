EXIT=
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME}"   # Secret from env
DOCKERHUB_PASSWORD="${DOCKERHUB_PASSWORD}"   # Secret from env

while (( $# ))
do
  case $1 in
    --source|-s)
      shift
      SOURCE=$1
      ;;
    --dest|-d)
      shift
      DEST=$1
      ;;
  esac
  shift
done

conditional_exit() {
  if test -n "${EXIT}"
  then
    exit $EXIT
  fi
}

if test -z "${SOURCE}"
then
  echo "No --source/-s provided."
  EXIT=1
fi
if test -z "${DEST}"
then
  echo "No --dest/-d provided."
  EXIT=1
fi

set -e

conditional_exit

echo "${DOCKERHUB_PASSWORD}" | docker login -u ${DOCKERHUB_USERNAME} --password-stdin

echo "Tagging image ${SOURCE} as ${DEST}."
docker pull "${SOURCE}"
docker tag "${SOURCE}" "${DEST}"
docker push "${DEST}"
echo "Push to ${DEST} successful."
