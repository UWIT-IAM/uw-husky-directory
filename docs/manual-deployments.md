# Manual deployments to dev

If you need to deploy to dev manually, instead of going through a pull request first 
(which may be the case if you need to check an otherwise mocked integration), you 
can do this easily with the following commands:

```
IMAGE=uwitiam/husky-directory:deploy-dev.commit-${USER}-$(date +%Y-%m-%dT%h-%m)
docker build -f docker/development-server.dockerfile -t ${IMAGE}
docker push ${IMAGE}
```

**This requires dockerhub credentials** for now. I (Tom) can give some to you if you 
need them. Soon we'll migrate this to gcr.io so that we won't have to deal with a 
separate third-party product. (I am currently working on this migration, it won't be 
long.)

You should only have to do a manual deployment if what you are changing is not 
testable on your local machine, e.g., something with a real IdP. (See also EDS-560.)
