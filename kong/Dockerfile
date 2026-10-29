FROM kong:3.9
ENV KONG_DATABASE=off
ENV KONG_DECLARATIVE_CONFIG=/kong/kong.yml
COPY kong.yml /kong/kong.yml
RUN kong config parse /kong/kong.yml
