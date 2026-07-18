FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/medreg \
    EMBEDDING_CACHE_DIR=/var/cache/medreg-fastembed

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates fonts-wqy-zenhei libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 medreg \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin medreg \
    && mkdir -p /app/backend /var/cache/medreg-fastembed \
    && chown -R medreg:medreg /app /var/cache/medreg-fastembed

WORKDIR /app/backend

COPY --chown=medreg:medreg backend/pyproject.toml ./pyproject.toml
COPY --chown=medreg:medreg backend/src ./src
COPY --chown=medreg:medreg backend/alembic ./alembic
COPY --chown=medreg:medreg backend/alembic.ini ./alembic.ini
COPY scripts/container-entrypoint.sh /usr/local/bin/medreg-entrypoint

RUN chmod 0755 /usr/local/bin/medreg-entrypoint \
    && python -m pip install --no-cache-dir .

USER 10001:10001

EXPOSE 8200

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8200/api/v1/health', timeout=3)"

ENTRYPOINT ["/usr/local/bin/medreg-entrypoint"]
CMD ["uvicorn", "medreg.main:app", "--host", "0.0.0.0", "--port", "8200"]
