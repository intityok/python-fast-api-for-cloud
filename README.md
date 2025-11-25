# Data Adaptor API

FastAPI-based middleware service for Grafana to fetch data from multiple sources (DSM, Mikrotik, NVR) with proper authentication handling.

## Overview

This service acts as an API middleware to consolidate data from multiple systems that require different authentication methods:

- **Synology DSM**: Requires token-based authentication (2-step API calls)
- **Mikrotik Routers**: Basic authentication
- **NVR (Dahua)**: Digest authentication

Grafana can query a single endpoint from this service instead of managing multiple authentication flows.

## Features

- Async HTTP requests for better performance
- Proper digest authentication implementation for NVR
- Environment-based configuration
- Clean error handling
- SSL verification disabled for internal networks (configurable)

## Endpoints

| Endpoint | Source | Description |
|----------|--------|-------------|
| `GET /dsmwatchdog` | Synology DSM | System utilization data |
| `GET /2011watchdog` | Mikrotik RB2011 | System resource data |
| `GET /4011watchdog` | Mikrotik RB4011 | System resource data |
| `GET /nvrsummary` | NVR | System information |
| `GET /nvrslowspace` | NVR | Low space configuration |
| `GET /nvrshddfail` | NVR | Storage failure config |
| `GET /nvrhealth` | NVR | Storage health status |
| `GET /nvrrecordstatus` | NVR | Recording status |

## Installation

### Prerequisites

- Python 3.8 or higher
- pip

### Setup

1. **Clone or navigate to the project directory**

```bash
cd dataadaptor
```

2. **Create a virtual environment (recommended)**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Synology DSM Configuration
DSM_URL=https://your-dsm-url
DSM_USER=your-username
DSM_PASS=your-password

# Mikrotik Configuration
MIKROTIK_2011_URL=https://your-mikrotik-2011-url
MIKROTIK_4011_URL=https://your-mikrotik-4011-url
MIKROTIK_USER=your-username
MIKROTIK_PASS=your-password

# NVR Configuration
NVR_URL=http://your-nvr-url:port
NVR_USER=your-username
NVR_PASS=your-password
```

## Running the Service

### Development Mode

```bash
# Using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or using Python
python main.py
```

The API will be available at `http://localhost:8000`

### Production Mode

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Documentation

FastAPI automatically generates interactive API documentation:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Usage Examples

### Test endpoints with curl

```bash
# DSM watchdog
curl http://localhost:8000/dsmwatchdog

# Mikrotik 2011
curl http://localhost:8000/2011watchdog

# NVR summary
curl http://localhost:8000/nvrsummary
```

### Configure in Grafana

In your Grafana data source configuration:

1. Add a JSON API data source
2. Set URL to: `http://your-server:8000/dsmwatchdog` (or any other endpoint)
3. No authentication needed (handled by the middleware)

## Deployment Options

### Using systemd (Linux)

Create `/etc/systemd/system/dataadaptor.service`:

```ini
[Unit]
Description=Data Adaptor API
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/dataadaptor
Environment="PATH=/path/to/dataadaptor/venv/bin"
ExecStart=/path/to/dataadaptor/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable dataadaptor
sudo systemctl start dataadaptor
```

### Using Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t dataadaptor .
docker run -d -p 8000:8000 --env-file .env dataadaptor
```

## Security Notes

- The service disables SSL verification (`verify=False`) for internal network requests. If your services have valid SSL certificates, remove this parameter.
- Store credentials securely using `.env` file and never commit it to version control
- Consider using a reverse proxy (nginx) with SSL for production deployments
- Implement rate limiting if exposing to untrusted networks

## Troubleshooting

### 401 Errors

- Check credentials in `.env` file
- Verify the user has proper permissions on the source systems
- For DSM, ensure the API is enabled

### Connection Errors

- Verify URLs in `.env` are correct and accessible from the server
- Check firewall rules
- Ensure services are running on the specified ports

### Digest Authentication Issues

- The digest auth implementation should work with most RFC 2617 compliant servers
- If you encounter issues, check server logs for the expected authentication format

## Migration from Node-RED

This Python implementation replaces the Node-RED flow with:

1. **Better digest authentication**: Native Python implementation instead of custom Node-RED function
2. **Environment configuration**: Centralized credential management
3. **Better error handling**: Proper HTTP exceptions and error messages
4. **Type safety**: Clear function signatures and return types
5. **Documentation**: Auto-generated API docs via FastAPI

## License

MIT
