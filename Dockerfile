FROM astral/uv:python3.14-alpine

WORKDIR /server

COPY pyproject.toml uv.lock /server/
COPY mcp_server /server/mcp_server

RUN uv sync --locked

EXPOSE 8000

CMD ["uv", "run", "--no-project", "mcp_server/app.py"]
