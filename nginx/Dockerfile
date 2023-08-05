FROM nginx:1.21-alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d
COPY ocean.crt /etc/ssl/certs/ocean.crt
COPY ocean.key /etc/ssl/private/ocean.key