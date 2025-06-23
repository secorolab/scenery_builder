# syntax=docker/dockerfile:1
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update
RUN apt install -y software-properties-common git
RUN apt install -y python3 python3-pip
RUN apt install -y blender


WORKDIR /usr/src/app/modules
WORKDIR /tmp
COPY . .
RUN pip install . -t /usr/src/app/modules

ENV BLENDER_USER_SCRIPTS=/usr/src/app

WORKDIR /usr/src/app/

ENTRYPOINT ["blender", "-b", "--python", "modules/fpm/cli.py", "--", "generate"]

CMD ["-i", "/usr/src/app/models/", "--output-path", "/usr/src/app/output/", "mesh", "tasks", "gazebo", "occ-grid", "polyline", "door-keyframes"]