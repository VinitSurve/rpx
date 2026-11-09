# Multi-stage minimal production Dockerfile for RPX
# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip build wheel && \
    python -m build --wheel

# Runtime image
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="RPX" \
      org.opencontainers.image.description="Repository Project Explorer | Comprehensive Local-First Developer Utility" \
      org.opencontainers.image.url="https://github.com/VinitSurve/rpx" \
      org.opencontainers.image.source="https://github.com/VinitSurve/rpx" \
      org.opencontainers.image.licenses="MIT"

# Install git for repository analytics
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create a non-privileged system user and group
RUN groupadd -g 10001 rpxuser && \
    useradd -u 10001 -g rpxuser -s /bin/sh -m rpxuser

# Install built wheel from builder stage
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

# Workspace mount point
WORKDIR /workspace

# Switch to non-root user
USER 10001:10001

# Default entrypoint
ENTRYPOINT ["rpx"]
CMD ["--help"]

