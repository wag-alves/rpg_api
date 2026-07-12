FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for all runtimes
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg lsb-release software-properties-common \
    libicu-dev libssl-dev \
    python3-pip python3.12-venv python3.12-dev \
    rabbitmq-server \
    && rm -rf /var/lib/apt/lists/*

# === Node.js 22 LTS ===
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# === Go 1.22 ===
RUN curl -fsSL https://go.dev/dl/go1.22.10.linux-amd64.tar.gz | tar -C /usr/local -xz
ENV PATH=$PATH:/usr/local/go/bin

# === .NET SDK 10.0 ===
RUN curl -fsSL https://dot.net/v1/dotnet-install.sh | bash /dev/stdin \
    --channel 10.0 \
    --install-dir /usr/share/dotnet \
    && ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet

# Verify runtimes
RUN python3 --version \
    && node --version \
    && npm --version \
    && go version \
    && dotnet --version
