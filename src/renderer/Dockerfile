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
    zlib-dev \
    tor \
    vlc \
    && rm -rf /var/cache/apk/*

# Install Python dependencies
RUN python3 -m pip install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir --prefer-binary -r requirements.txt

# Copy application code
COPY src/renderer/ .
COPY src/modules/ ./modules
COPY src/logging_config.py .

EXPOSE 1337
CMD ["python3", "telnet_server.py"]
