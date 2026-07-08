FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Railway provides $PORT at runtime
ENV MCP_TRANSPORT=sse
ENV HOST=0.0.0.0

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

# Start the MCP server via entrypoint script
CMD ["bash", "entrypoint.sh"]
