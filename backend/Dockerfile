FROM python:3.12-slim

WORKDIR /app

# System dependencies for PDF generation and general build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create necessary directories
RUN mkdir -p uploads chroma_db data/compliance_rules

# Copy compliance rules from repo-level NFRA_Challenge_Data if available
# (docker-compose also mounts them, but this ensures they're baked in)
COPY data/compliance_rules/ data/compliance_rules/

# Make entrypoint executable
RUN chmod +x entrypoint.sh

EXPOSE 8888

ENTRYPOINT ["./entrypoint.sh"]
