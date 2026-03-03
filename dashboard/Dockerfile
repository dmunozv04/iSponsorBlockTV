# Build Frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY dashboard/frontend/package*.json ./
RUN npm install
COPY dashboard/frontend/ .
RUN npm run build

# Setup Backend
FROM python:3.13-slim
WORKDIR /app

# Install dependencies
COPY dashboard/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY dashboard/backend/ .

# Copy project source for reuse
COPY src /app/src

# Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist /app/static

# Expose port
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
