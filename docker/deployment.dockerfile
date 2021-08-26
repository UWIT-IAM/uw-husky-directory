# This image only exists as a final layer to add on top
# in order for flux to ALWAYS deploy. This is likely temporary,
# as flux v2 should give us more flexibility in how we deploy.
ARG IMAGE
FROM ${IMAGE} AS deployment
ARG DEPLOYMENT_ID
ENV DEPLOYMENT_ID=${DEPLOYMENT_ID} \
    FLASK_ENV=production
RUN echo $DEPLOYMENT_ID >> .deployment
CMD poetry run gunicorn -b 0.0.0.0:${FLASK_PORT} \
    --log-level ${GUNICORN_LOG_LEVEL} \
    -c "/app/husky_directory/gunicorn.conf.py" \
    --preload \
    "husky_directory.app:create_app()"
