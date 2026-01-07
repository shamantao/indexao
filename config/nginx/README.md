# Indexao Nginx Setup

## Installation

### Option 1: Docker nginx (recommended)

If you're using the docker-pbwww nginx container:

1. Copy the configuration:

```bash
cp nginx/indexao.conf /path/to/docker-pbwww/nginx/conf/indexao-nginx.conf
```

2. Restart nginx:

```bash
docker-compose -f /path/to/docker-pbwww/docker-compose.yml restart nginx
```

3. Add to `/etc/hosts`:

```
127.0.0.1 indexao.localhost
```

4. Start indexao:

```bash
cd /path/to/indexao
source venv/bin/activate
python -m indexao.webui
```

5. Access: http://indexao.localhost

### Option 2: Local nginx

1. Copy config to nginx:

```bash
sudo cp nginx/indexao.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/indexao.conf /etc/nginx/sites-enabled/
```

2. Test and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

3. Add to `/etc/hosts`:

```
127.0.0.1 indexao.localhost
```

## Configuration Notes

- **Port**: Indexao runs on port 8000
- **Upload limit**: 100MB (configurable via `client_max_body_size`)
- **Timeouts**: 300s for long-running operations
- **Logs**: Check `/var/log/nginx/indexao-*.log`

## Troubleshooting

### Connection refused

- Ensure indexao is running: `curl http://127.0.0.1:8000/health`
- Check docker networking: use `host.docker.internal` instead of `localhost`

### 413 Entity Too Large

- Increase `client_max_body_size` in nginx config

### Slow uploads

- Increase proxy timeouts in nginx config
