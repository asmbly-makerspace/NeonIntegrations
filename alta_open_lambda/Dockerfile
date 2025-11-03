FROM ghcr.io/astral-sh/uv AS uv

FROM public.ecr.aws/lambda/python:3.13-arm64 AS builder

# Set uv environment variables
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_NO_INSTALLER_METADATA=1

WORKDIR ${LAMBDA_TASK_ROOT}

# Install dependencies
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv export --frozen --no-emit-workspace --no-dev --no-editable -o requirements.txt && \
    uv pip install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Production stage
FROM public.ecr.aws/lambda/python:3.13-arm64 AS production

# Copy application from builder
COPY --from=builder ${LAMBDA_TASK_ROOT} ${LAMBDA_TASK_ROOT}

ENV PYTHONUNBUFFERED=1

COPY . ${LAMBDA_TASK_ROOT}

CMD ["alta_open_lambda.lambda_function.lambda_handler"]