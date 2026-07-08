FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Railway provides $PORT at runtime
ENV MCP_TRANSPORT=sse
ENV HOST=::

# Start the MCP server directly
CMD ["python", "-m", "src.server"]
