# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

RUN apt update && \
    apt install -y git \
    blender --no-install-recommends \
     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

RUN python -m pip install --upgrade pip

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml,rw=true \
    --mount=type=bind,source=.git,target=.git \
    --mount=type=bind,source=docs,target=docs \
    mkdir src \
    && python -m pip install . --no-cache-dir

# Copy the rest of the application
COPY . .

# Install the application itself
RUN pip install --no-cache-dir --no-deps . \
    && rm -rf .git

# Switch to the non-privileged user to run the application.
USER appuser

CMD ["floorplan" ,"generate", "-i", "/usr/src/app/models/", "-o", "/usr/src/app/output/", "mesh", "tasks", "gazebo", "occ-grid", "polyline", "door-keyframes"]