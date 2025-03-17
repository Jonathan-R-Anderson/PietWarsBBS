FROM alpine:3.14

WORKDIR /app

COPY . .

# Install necessary system dependencies for ncurses and Python
RUN apk add --no-cache \
    python3 \
    py3-pip \
    build-base \
    ncurses \
    ncurses-dev \
    && rm -rf /var/cache/apk/*


# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python3", "render_game.py"]
