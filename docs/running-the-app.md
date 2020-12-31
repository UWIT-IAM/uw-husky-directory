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
