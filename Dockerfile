FROM python:3.12-slim-bullseye

# Update package manager and install Python utilities
RUN apt-get update && \
    apt-get install -y --no-install-recommends locales && \
    echo "ru_RU.UTF-8 UTF-8" >> /etc/locale.gen && \
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && \
    locale-gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Create logs directory
RUN mkdir -p /app/logs

# Create volume for logs
VOLUME /app/logs

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Run the bot
CMD ["python3", "bot.py"]