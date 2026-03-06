# syntax=docker/dockerfile:1
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && \
    apt install -y software-properties-common git \
    python3 python3-pip \
    blender


WORKDIR /tmp

# Copy only dependency files first to leverage Docker cache
#COPY pyproject.toml .
#COPY .git .
#COPY docs/ .
#RUN mkdir src

# Install dependencies separately (this layer will be cached)
# RUN pip install --no-cache-dir . -t /usr/src/app/modules

# Copy the rest of the application
COPY . .

# Install the application itself
#RUN pip install --no-cache-dir --no-deps . -t /usr/src/app/modules && rm -rf .git
RUN pip install . -t /usr/src/app/modules && rm -rf .git

ENV BLENDER_USER_SCRIPTS=/usr/src/app

WORKDIR /usr/src/app/

ENTRYPOINT ["blender", "-b", "--python", "modules/fpm/cli.py", "--"]

CMD ["generate", "-i", "/usr/src/app/models/", "--output-path", "/usr/src/app/output/", "mesh", "tasks", "gazebo", "occ-grid", "polyline", "door-keyframes"]