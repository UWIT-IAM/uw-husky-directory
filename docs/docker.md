# DockerHub Images

. . .

## development-server

The [development-server]() image 


## poetry-base

The [poetry-base]() image is a relatively static image that shouldn't need updating 
very often. It is responsible for giving us a base platform with a properly configured 
python and poetry environment.

This should only be updated if we need to refresh or update python itself, or its
poetry installation:

```
docker build -f docker/poetry-base -t uwitiam/poetry-base .`
docker push -t uwitiam/poetry-base
```

Storing this layer separately speeds up our builds substantially, as this hefty
layer can then be cached.

