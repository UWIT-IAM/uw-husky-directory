# Manual deployments to dev

If you need to deploy to dev manually, instead of going through a pull request first 
(which may be the case if you need to check an otherwise mocked integration), you 
can do this easily with the following commands:

```
IMAGE=us-docker.pkg.dev/uwit-mci-iam/containers/husky-directory:deploy-dev.commit-${USER}-$(date +%Y-%m-%dT%h-%m)
docker build -f docker/development-server.dockerfile -t ${IMAGE}
docker push ${IMAGE}
```

You should only have to do a manual deployment if what you are changing is not 
testable on your local machine, e.g., something with a real IdP. (See also EDS-560.)
