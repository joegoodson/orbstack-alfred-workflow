# OrbStack Alfred Workflow

A powerful Alfred workflow for managing Docker containers running under OrbStack on macOS. Quickly list, control, and access your containers directly from Alfred.

## Features

- **🚀 Fast container listing** - See all running and stopped containers instantly
- **🌐 One-click URL access** - Open `orb.local` domains with a single keystroke
- **⚡ Container controls** - Start, stop, restart containers from Alfred
- **📊 Project management** - Batch operations on Docker Compose projects
- **🔍 Logs and shell access** - Quick access to container logs and interactive shells
- **📋 Smart actions** - Context-aware default actions based on container type

## Installation

### Requirements

- macOS 13.0 or later
- Alfred 5+ with Powerpack
- OrbStack installed and running
- Docker CLI available in PATH

### Setup

1. **Download the workflow** - Get the latest `.alfredworkflow` file from releases
2. **Import to Alfred** - Double-click the file to import into Alfred
3. **Configure PATH** - Ensure Alfred can find Docker CLI:
   - Open Alfred Preferences → Features → Terminal
   - Add `/opt/homebrew/bin` (Apple Silicon) or `/usr/local/bin` (Intel) to PATH
   - Or set Alfred's PATH to include your Docker installation

### Verify Installation

1. Type `orb` in Alfred
2. You should see a list of your OrbStack containers
3. If you see "Docker not found", check the PATH configuration above

## Usage

### Basic Commands

Type `orb` in Alfred to see all containers. Each container shows:
- **Title**: Service name or container name
- **Subtitle**: Project • status • resource usage • health

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `↵ Enter` | Smart default action (URL for web services, shell for others) |
| `⌘ Cmd+↵` | Open orb.local URL in browser |
| `⌥ Alt+↵` | Start stopped container / Stop running container |
| `⌃ Ctrl+↵` | Show container logs in Terminal |
| `⇧ Shift+↵` | Copy orb.local URL to clipboard |

### URL Derivation

The workflow automatically derives `orb.local` URLs:

- **Docker Compose services**: `https://service.project.orb.local/`
- **Standalone containers**: `https://container-name.orb.local/`

### Project Batch Actions

When multiple containers belong to the same Docker Compose project, you'll see project-level actions:
- **📦 project-name** - Start/stop all containers in the project

### Web Service Detection

The workflow uses heuristics to detect web services:
- Containers exposing ports 80/443 or with port mappings
- Names/services containing: web, app, frontend, ui
- Images containing: nginx, httpd, caddy, traefik, node, python

## Configuration

### Environment Variables

Create a `.env` file in the workflow directory to customize behavior:

```bash
# Default action when pressing Enter (auto|url|shell)
DEFAULT_OPEN_ACTION=auto

# URL scheme for orb.local domains
URL_SCHEME=https

# Log tail duration
LOGS_SINCE=10m

# Cache TTL in milliseconds
CACHE_TTL_MS=2000

# Fallback shell for containers
FALLBACK_SHELL=/bin/sh

# Enable debug logging
DEBUG=0
```

### Debug Mode

Enable debug logging by setting `DEBUG=1` in your `.env` file. Logs are written to `~/Library/Logs/orb-alfred.log`.

## Troubleshooting

### "Docker not found" Error

This means Alfred can't find the Docker CLI. Solutions:

1. **Check OrbStack installation**:
   ```bash
   which docker
   # Should return: /usr/local/bin/docker or /opt/homebrew/bin/docker
   ```

2. **Update Alfred's PATH**:
   - Alfred Preferences → Features → Terminal → Shell / PATH
   - Add `/opt/homebrew/bin:/usr/local/bin` to the PATH

3. **Verify Docker context**:
   ```bash
   docker context current
   # Should return: orbstack
   ```

### "No containers found"

1. Check if OrbStack is running
2. Verify you have containers: `docker ps -a`
3. Ensure Docker daemon is accessible

### Slow Performance

1. Reduce `CACHE_TTL_MS` in `.env` for more frequent updates
2. Check Docker daemon responsiveness: `docker ps --format "table {{.Names}}"`
3. Restart OrbStack if commands are timing out

### URL Not Opening

1. Verify the container is actually serving content
2. Check if the container exposes the expected ports
3. Test the URL manually in a browser
4. Ensure OrbStack's DNS resolution is working

### Shell/Logs Not Working

1. Ensure Terminal.app has proper permissions
2. Check if the container is running: status should show "running"
3. Verify the container has a shell: `docker exec <container> which sh`

## Development

### Project Structure

```
orbstack-alfred/
├── README.md
├── LICENSE
├── pyproject.toml
├── workflow/
│   ├── info.plist              # Alfred workflow configuration
│   ├── icon.png                # Workflow icon
│   ├── scripts/
│   │   ├── script_filter.py    # Container listing logic
│   │   ├── dispatcher.py       # Action handler
│   │   └── helpers.py          # Core utilities
│   └── .env.example            # Configuration template
└── tests/
    ├── fixtures/               # Test data
    └── test_*.py              # Unit tests
```

### Running Tests

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Run tests
uv run python -m pytest tests/

# Run specific test
uv run python tests/test_url_derivation.py
```

### Building the Workflow

```bash
# Create the .alfredworkflow package
cd workflow
zip -r ../OrbStack-Alfred-Workflow.alfredworkflow .
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Changelog

### v1.0.0
- Initial release
- Container listing and management
- URL derivation and opening
- Project batch actions
- Logs and shell access
- Comprehensive test suite

## Support

- **Issues**: Report bugs and request features on GitHub
- **Documentation**: This README and inline code comments
- **Community**: Discussions on GitHub

---

**Made with ❤️ for the OrbStack and Alfred communities**