FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Railway provides $PORT at runtime
ENV MCP_TRANSPORT=streamable-http
ENV HOST=0.0.0.0

# Start the MCP server
CMD ["python", "-m", "src.server"]
