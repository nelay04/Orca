# Use an official Python image
# python:3.13-slim is roughly 100MB, with lightweight Python and minimal OS tools
FROM python:3.13-slim

# Prevents Python from writing .pyc
ENV PYTHONDONTWRITEBYTECODE=1

# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Port the app listens on inside the container. Override at build time with
#   docker build --build-arg PORT=9000 .
# or at run time by setting PORT in the environment, which entrypoint.sh reads.
ARG PORT=8004
ENV PORT=${PORT}

# Set the working directory in the container
WORKDIR /app

# Install Python packages first so this layer is cached across code changes
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy the whole project folder into the container
COPY . .

# Make sure entrypoint.sh is executable
RUN chmod +x /app/entrypoint.sh

# Invoked through sh rather than directly. docker-compose bind-mounts the
# project over /app, which replaces the executable bit set above with whatever
# the host file carries, and clones on Windows often drop it entirely.
ENTRYPOINT ["sh", "/app/entrypoint.sh"]

# Documents the port the app listens on. Publishing it is done by
# docker-compose.yml or `docker run -p`.
EXPOSE ${PORT}
