# IS MUNI MCP — read-only MCP server pro studenty MU.
# Stdio (výchozí):  docker run -i --rm -v is-muni-config:/config -e XDG_CONFIG_HOME=/config is-muni-mcp
# HTTP (vzdálený přístup): docker run --rm -p 8000:8000 ... is-muni-mcp serve --transport streamable-http --host 0.0.0.0
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CONFIG_HOME=/config

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

VOLUME /config
ENTRYPOINT ["is-muni-mcp"]
CMD []
