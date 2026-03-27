FROM python:3.13-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only the files needed to install the package to keep the build cache warm.
COPY pyproject.toml README.md ./
COPY cli ./cli
COPY tradingagents ./tradingagents
COPY main.py ./main.py

RUN pip install --no-cache-dir .

CMD ["python", "-m", "cli.main"]

FROM tsl0922/ttyd:latest AS ttyd-binary

FROM base AS web

COPY --from=ttyd-binary /usr/bin/ttyd /usr/local/bin/ttyd
COPY docker/web_entrypoint.sh /usr/local/bin/web_entrypoint.sh
COPY docker/web_terminal.sh /usr/local/bin/web_terminal.sh

RUN chmod +x /usr/local/bin/web_entrypoint.sh /usr/local/bin/web_terminal.sh

EXPOSE 7681

CMD ["/usr/local/bin/web_entrypoint.sh"]
