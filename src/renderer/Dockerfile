FROM alpine:3.14

WORKDIR /app

COPY . .

# Install Python runtime
RUN apk add --no-cache \
    python3 \
    py3-pip \
    build-base \
    python3-dev \
    && rm -rf /var/cache/apk/*


# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 8023
CMD ["python3", "telnet_server.py"]
