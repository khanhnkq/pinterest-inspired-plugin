FROM python:3.12-slim

# Install uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /bin/uv

WORKDIR /app

# Copy project specifications
COPY pyproject.toml uv.lock README.md ./

# Install dependencies without installing root project in editable mode
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ src/

# Install project into virtualenv
RUN uv sync --frozen --no-dev

# Set runtime environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=sse \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8085

EXPOSE 8085

CMD ["python", "-m", "src.server"]
