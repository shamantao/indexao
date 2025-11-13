# Indexao Quick Start Guide

Version: 0.3.1-dev  
Date: November 13, 2025

## Services

### Start All Services

```bash
# Meilisearch
cd /Users/phil/pCloudSync/Projets/meilisearch
./start-meilisearch.sh

# Indexao Web UI
cd /Users/phil/Library/CloudStorage/Dropbox/devwww/app/indexao
source venv/bin/activate
python -m indexao.webui
```

### URLs

- **Web UI**: http://indexao.localhost/ (via Nginx)
- **Direct API**: http://127.0.0.1:8000/
- **Meilisearch**: http://localhost:7700/
- **Meilisearch UI**: http://localhost:24900/

## Key Features (v0.3.1)

### 1. Cloud Volume Management

Access: http://indexao.localhost/config → Tab "Volumes Cloud"

**Add a volume:**
1. Click "Ajouter un volume"
2. Fill: name, path, index name, file patterns
3. Click "Ajouter"

**Scan a volume:**
- Click "Scanner maintenant" button on volume card
- Progressive indexing: 50-100 files/batch
- Monitor progress with progress bar

**API:**
```bash
# List volumes
curl http://127.0.0.1:8000/api/cloud/volumes

# Add volume
curl -X POST http://127.0.0.1:8000/api/cloud/volumes \
  -H "Content-Type: application/json" \
  -d '{"name":"mycloud","mount_path":"/path/to/cloud","index_name":"mycloud_docs"}'

# Scan volume
curl -X POST http://127.0.0.1:8000/api/cloud/volumes/mycloud/scan

# Delete volume
curl -X DELETE http://127.0.0.1:8000/api/cloud/volumes/mycloud
```

### 2. Framework Manager

**Check status:**
```bash
curl http://127.0.0.1:8000/api/frameworks/status
```

**Download frameworks:**
```bash
# Download all
curl -X POST http://127.0.0.1:8000/api/frameworks/download

# Download specific
curl -X POST http://127.0.0.1:8000/api/frameworks/download \
  -H "Content-Type: application/json" \
  -d '["alpine","htmx","fontawesome"]'
```

**Check updates:**
```bash
curl http://127.0.0.1:8000/api/frameworks/check-updates
```

### 3. Meilisearch Proxy

**List indexes:**
```bash
curl http://127.0.0.1:8000/api/meilisearch/indexes
```

**Create index:**
```bash
curl -X POST http://127.0.0.1:8000/api/meilisearch/indexes \
  -H "Content-Type: application/json" \
  -d '{"uid":"my_index","primaryKey":"id"}'
```

**Delete index:**
```bash
curl -X DELETE http://127.0.0.1:8000/api/meilisearch/indexes/my_index
```

## Development

### Install Dependencies

```bash
cd /Users/phil/Library/CloudStorage/Dropbox/devwww/app/indexao
source venv/bin/activate
pip install -r requirements.txt
```

### Run Tests

```bash
# All tests
pytest

# Specific module
pytest tests/test_cloud_indexer.py -v

# With coverage
pytest --cov=indexao tests/
```

### Code Quality

```bash
# Format with black
black src/indexao/

# Lint with flake8
flake8 src/indexao/

# Type check with mypy
mypy src/indexao/
```

## Configuration

### Cloud Indexer

Edit: `data/cloud_indexer_state.json`

```json
{
  "volumes": {
    "pcloud_drive": {
      "mount_path": "/Users/phil/pCloud Drive",
      "index_name": "pcloud_drive",
      "enabled": true,
      "file_patterns": ["*.pdf", "*.doc", "*.docx", "*.txt"]
    }
  }
}
```

### Meilisearch

Edit: `config.toml`

```toml
[plugins.search]
engine = "meilisearch"
url = "http://localhost:7700"
api_key = ""
```

## Troubleshooting

### Port already in use

```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 7700
lsof -ti:7700 | xargs kill -9
```

### Clear cache

```bash
# Clear Meilisearch data
rm -rf /Users/phil/pCloudSync/Projets/meilisearch/data.ms/*

# Clear Indexao state
rm -f data/cloud_indexer_state.json
```

### Restart services

```bash
# Restart Indexao
pkill -f "python -m indexao.webui"
cd /Users/phil/Library/CloudStorage/Dropbox/devwww/app/indexao
source venv/bin/activate
nohup python -m indexao.webui > /tmp/indexao.log 2>&1 &

# Check logs
tail -f /tmp/indexao.log
```

## Useful Commands

### Check Service Status

```bash
# Indexao
curl -s http://127.0.0.1:8000/api/frameworks/status | python3 -m json.tool

# Meilisearch
curl -s http://localhost:7700/health

# Check all
ps aux | grep -E "(indexao|meilisearch)" | grep -v grep
```

### Monitor Indexing Progress

```bash
# Watch cloud indexer state
watch -n 2 "cat data/cloud_indexer_state.json | python3 -m json.tool"

# Check logs
tail -f /tmp/indexao.log | grep -E "(indexed|progress|scan)"
```

## Standards

- **PEP8**: Python code style
- **Logger**: Use `from indexao.logger import get_logger`
- **PathAdapter**: Use for all file I/O operations
- **Testing**: Write tests for all new features
- **Documentation**: Update CHANGELOG.md for all versions

---

For detailed architecture and technical standards, see:
- `ARCH-tech.md` - Technical architecture
- `TECH-STANDARDS.md` - Development standards
- `CHANGELOG.md` - Version history
- `CLOUD-INDEXING.md` - Cloud indexing details
