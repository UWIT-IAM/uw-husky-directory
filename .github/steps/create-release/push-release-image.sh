
if [[ "${GITHUB_REF}" == "refs/heads/main" ]]
then
  docker pull $pr_image
else
  docker pull $testing_image
  docker tag $testing_image $pr_image
fi
docker tag $pr_image $release_image

if [[ "${GITHUB_REF}" == 'refs/heads/main' ]]
then
  docker push $release_image
  ./scripts/update-dependency-image.sh --push
else
  echo "Not pushing $release_image in dry-run mode."
fi
