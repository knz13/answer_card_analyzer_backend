# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container to /app
WORKDIR /app

# Add the current directory contents into the container at /app
ADD . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Poppler
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install OpenCV dependencies
RUN apt-get update && apt-get install -y \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Nginx
RUN apt-get update && apt-get install -y \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Copy the Nginx configuration file
COPY nginx.conf /etc/nginx/nginx.conf

# Copy the SSL certificate and private key
COPY server.crt /etc/nginx/server.crt
COPY server.key /etc/nginx/server.key

# Make port 80 and 443 available to the world outside this container
EXPOSE 80 443

# Start Nginx and the application
CMD service nginx start && python main_http.py