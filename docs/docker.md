# Docker Overview

We use docker to track, test, and deploy our builds. 

## Tagging Strategy

Images tagged with `commit-X` (where `X` is the first 10 characters of a commit hash)
refer to a development build against a specific git commit.

These build images, when attached to a pull request, will also be tagged with 
`pull-request-X`, where `X` is the PR number assigned by github. This will always 
reflect the latest build of the pull request; previous builds will still be 
accessible by their commit tag above.

Images tagged with `deploy-dev.commit-X` are images that were tagged for deployment 
to our [development environment](https://github.com/uwit-iam/gcp-k8/tree/master/dev/uw-directory).

Images tagged with a [sem ver](https://www.semver.org) `X.Y.Z` will be automatically 
deployed to our eval environment. (Which is not currently configured.)

Images tagged with both `prod` and a released sem ver tag (i.e., when one of those 
sem ver tags is also tagged with `prod`), then it will also be deployed to prod. 
(The prod environment is not currently configured.)

## Image Retention

This is a problem that still needs solving. See IAM-258.

## GCR Image Repository

The repository for this service is gcr.io/uwit-mci-iam/husky-directory. Access to 
this repository requires operator permissions on our google project. Team members 
can reach out on slack for access if they do not have it already.

### Github Actions access to gcr.io:

If the security token for Github Actions ever needs to be updated:

1. Create a new key for the `uw-directory-github-actions` service account. Download 
   the key. 
1. Base64 encode it. (`cat $KEY_FILE_NAME | base64`)
1. Update the `GCR_TOKEN` secret in the [github repository secrets] with the 
   base64-encoded value.

_This can only be done by a person who is an administrator of this repository, and 
has access to the project IAM configuration._

## Running images

Refer to docker documentation for advanced use cases.

You can run any published tag:

`./scripts/run-development-server.sh -i gcr.io/uwit-mci-iam/husky-directory:${TAG}`


## development-server dockerfile

The [development-server]
creates an application that is intended to be run for testing, validation, and 
user pre-release evaluation.


[development-server]: https://github.com/uwit-iam/uw-husky-directory/tree/main/docker/development-server.dockerfile 
[poetry-base]: https://gcr.io/uwit-mci-iam/poetry
[search-image-tags]: https://github.com/uwit-iam/uw-husky-directory/tree/main/scripts/search-image-tags.sh]
[commits]: commits.md
[gcr.io]: https://gcr.io/uwit-mci-iam/husky-directory
[github repository secrets]: https://github.com/UWIT-IAM/uw-husky-directory/settings/secrets/actions
