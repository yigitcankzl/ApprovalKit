FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY healthcare-agent/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install ApprovalKit SDK
COPY sdk/ /app/sdk/
RUN pip install --no-cache-dir /app/sdk/

# Copy application
COPY healthcare-agent/ .

# Expose port
EXPOSE 3002

# Run with uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "3002"]
