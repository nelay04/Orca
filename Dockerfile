# Use an official Python image
# Include Python 3.12 already ready to go inside the container
# python:3.12-slim	size≈100MB	with lightweight Python, minimal OS tools
FROM python:3.12-slim

# Prevents Python from writing .pyc
ENV PYTHONDONTWRITEBYTECODE=1    

# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Update the list of available packages, and clean up cached package list files after installation
RUN apt-get update && rm -rf /var/lib/apt/lists/*

# Check python version
RUN python3 --version

# Copies the requirements.txt file into the container at /app
COPY requirements.txt .

# Upgrade pip to the latest version & install all python packages listed in requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the whole project folder into the container
COPY . .

# Copy entrypoint script into the container
COPY entrypoint.sh /app/entrypoint.sh

# Make sure entrypoint.sh is executable
RUN chmod +x /app/entrypoint.sh

# Use entrypoint.sh to start the container
ENTRYPOINT ["/app/entrypoint.sh"]

# Purpose--Just a hint: "my app uses port 8004 internally"
EXPOSE 8004
