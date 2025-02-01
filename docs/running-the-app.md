# Running the UW Directory docker app

In order to run the app locally, you have to provide have a UWCA-signed certificate 
with PWS access (see [pws.md](pws.md)).

The docker app has to be mounted such that your certificate is available in the 
container at `/app/certificates`.

You can use: `./scripts/run-development-server.sh` to run the image, providing the 
path to your certificate and the name of your certificate. Note that your `.crt` 
file and your `.key` file must have the same name. (NB, if your cert file has a `.
pem` suffix, you can copy or rename it to have the `.crt` suffix instead.)

For instance, if you had the following directory structure on your laptop:

```
+ /Users/you
|- foo.crt
|- foo.key
```

You would run the dev server like this:

```
./scripts/run-development-server.sh --cert-path /Users/you --cert-name foo
```

(By default, the cert name is `uwca`; feel free to rename your cert/key so you don't 
have to provide this argument.)

**Running without a valid certificate is not supported at this time.** You can 
certainly try it, but you won't get very far since the application's main function 
is to query PWS.


## Options

**For complete documentation of the run-development-server.sh 
script, run it with `--help`**

You can run any published tag with `-i`:

`./scripts/run-development-server.sh -i us-docker.pkg.dev/uwit-mci-iam/containers/husky-directory:${TAG}`

You can run an instance that also uses a redis cache (for testing and validation
purposes) and includes a prometheus instance with:

`./.scripts/run-development-server.sh --compose`

This will use the [docker-compose file](../docker/docker-compose.app.yaml)
instead of a single docker container. Note that this automatically sets up the
environment to mount your code live (locally); this is not configurable without editing
the docker-compose file.

You can run an instance with updated dependencies by providing the `--rebuild-base`
flag. If you use `poetry add` to include a new dependency, you must use this
argument in order to run it, until you open a pull request to trigger an update. 
