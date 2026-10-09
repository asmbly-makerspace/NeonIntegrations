# Container image for the hosted Asmbly MCP server (AWS Lambda).
#
# Build from the REPO ROOT, because the server reuses neonUtil.py and openPathUtil.py:
#   docker build -f asmbly_mcp/Dockerfile .
# Normally you don't run that yourself: `sam build` does it (see DEPLOY.md).
#
# No API keys go into this image. They're read from AWS Parameter Store at startup.

FROM public.ecr.aws/docker/library/python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0

# Install exactly what asmbly_mcp/uv.lock pins
WORKDIR /build
COPY asmbly_mcp/pyproject.toml asmbly_mcp/uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o requirements.txt && \
    uv pip install -r requirements.txt --target /deps


FROM public.ecr.aws/docker/library/python:3.13-slim

# Lets an ordinary web server run on Lambda: it turns each Lambda request into
# an HTTP request to the server below. https://github.com/awslabs/aws-lambda-web-adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0 /lambda-adapter /opt/extensions/lambda-adapter

COPY --from=builder /deps /opt/deps

WORKDIR /var/task

# Copy only the files the server needs. Never `COPY . .` here: a developer's
# local config.py holds real API keys and must not end up in an image.
COPY neonUtil.py openPathUtil.py gmailUtil.py AsmblyMessageFactory.py ./
COPY asmbly_mcp/*.py ./asmbly_mcp/

ENV PYTHONPATH=/opt/deps \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Lambda's disk is read-only except /tmp
    HOME=/tmp \
    PORT=8080 \
    # the server library only logs warnings and errors, not routine activity
    FASTMCP_LOG_LEVEL=WARNING \
    # the adapter waits for this to answer before sending requests
    AWS_LWA_READINESS_CHECK_PATH=/health

# --no-access-log: request lines would put sign-in codes from the URL into the logs
CMD ["python", "-m", "uvicorn", "asmbly_mcp.hosted:createApp", "--factory", \
     "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
