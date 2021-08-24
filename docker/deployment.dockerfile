# This image only exists as a final layer to add on top
# in order for flux to ALWAYS deploy. This is likely temporary,
# as flux v2 should give us more flexibility in how we deploy.
ARG IMAGE
ARG DEPLOYMENT_ID
FROM IMAGE AS release
ENV DEPLOYMENT_ID=${DEPLOYMENT_ID}
