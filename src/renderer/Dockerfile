FROM alpine:3.14

WORKDIR /app

# Copy only renderer requirements first for better caching
COPY src/renderer/requirements.txt ./requirements.txt

# Install Python runtime
RUN apk add --no-cache \
    python3 \
    py3-pip \
    build-base \
    python3-dev \
    && rm -rf /var/cache/apk/*

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/renderer/ .
COPY src/modules/ ./modules

EXPOSE 1337
CMD ["python3", "telnet_server.py"]
