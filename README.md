# html-readability-extractor

A Flask microservice that extracts main content text from HTML using readability-lxml and BeautifulSoup.

## Features

- **POST /extract-text**: Extract readable text from HTML content
  - Accepts JSON payload: `{"html": "..."}`
  - Returns JSON response: `{"text": "...", "length": N}`
  - Uses readability-lxml for main content extraction
  - Uses BeautifulSoup to remove script/style tags
  - Normalizes whitespace
  - Requires Basic Authentication

- **GET /health**: Health check endpoint (no authentication required)
  - Returns: `{"status": "healthy"}`

## Configuration

Configure the service using environment variables:

- `BASIC_AUTH_USERNAME`: Username for Basic Authentication (default: `admin`)
- `BASIC_AUTH_PASSWORD`: Password for Basic Authentication (default: `password`)
- `FLASK_HOST`: Host to bind the Flask application (default: `0.0.0.0`)
- `FLASK_PORT`: Port to bind the Flask application (default: `5000`)
- `FLASK_DEBUG`: Enable debug mode (default: `false`)

## Quick Start

### Using Docker Compose

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your desired configuration

3. Start the service:
```bash
docker-compose up -d
```

### Using Docker

Build and run the Docker image:
```bash
docker build -t html-readability-extractor .
docker run -p 5000:5000 \
  -e BASIC_AUTH_USERNAME=admin \
  -e BASIC_AUTH_PASSWORD=password \
  html-readability-extractor
```

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export BASIC_AUTH_USERNAME=admin
export BASIC_AUTH_PASSWORD=password
```

3. Run the application:
```bash
python app.py
```

## Usage Examples

### Health Check

```bash
curl http://localhost:5000/health
```

Response:
```json
{"status": "healthy"}
```

### Extract Text

```bash
curl -X POST http://localhost:5000/extract-text \
  -u admin:password \
  -H "Content-Type: application/json" \
  -d '{"html": "<html><body><h1>Title</h1><p>Content</p><script>alert(1)</script></body></html>"}'
```

Response:
```json
{
  "text": "Title Content",
  "length": 13
}
```

## CI/CD

The repository includes a GitHub Actions workflow that automatically:
- Builds the Docker image on push to the `main` branch
- Pushes the image to GitHub Container Registry at `ghcr.io/{owner}/{repo}:latest`

## Logging

All logs are written to stdout in a structured format for easy integration with logging systems.