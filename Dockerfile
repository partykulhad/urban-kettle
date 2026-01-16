FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the polling server
COPY polling_server2.py .

# Expose port 5000
EXPOSE 5000

# Run the server
CMD ["python", "polling_server2.py"]
