#!/usr/bin/env python3
"""
Helper utilities for OrbStack Alfred Workflow
Handles Docker operations, caching, URL derivation, and container analysis
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


# Common ports used by web services (container-side)
COMMON_WEB_PORTS = {
    80, 443, 3000, 3001, 4000, 5000, 5001, 7000, 7001,
    8000, 8001, 8080, 8081, 8888, 4200, 5173
}

# Names that suggest a container is not a website even if it matches other heuristics
NEGATIVE_SERVICE_KEYWORDS = (
    'db', 'database', 'postgres', 'mysql', 'mariadb', 'mongo', 'redis',
    'cache', 'worker', 'queue', 'scheduler', 'job', 'task', 'celery',
    'rabbit', 'message', 'broker', 'minio', 's3'
)

# Positive hints that usually point at a user-facing web service
POSITIVE_SERVICE_KEYWORDS = (
    'web', 'frontend', 'ui', 'client', 'site'
)

# Images that are typically web servers or frameworks serving HTTP
WEB_IMAGE_KEYWORDS = (
    'nginx', 'httpd', 'caddy', 'traefik', 'haproxy', 'node', 'python',
    'gunicorn', 'uwsgi', 'apache', 'php', 'rails', 'django', 'flask',
    'nextjs', 'nuxt', 'vite', 'express'
)


def clean_project_name(project: Optional[str]) -> str:
    """Return a human-friendly project name"""
    if not project:
        return ''

    cleaned = project.replace('_', ' ').replace('-', ' ')
    cleaned = re.sub(r'^\d+\s*', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


class Config:
    """Configuration management from environment and .env file"""
    
    def __init__(self):
        # Load from .env file if it exists
        env_file = Path(__file__).parent.parent / '.env'
        if env_file.exists():
            self._load_env_file(env_file)
        
        # Configuration with defaults
        self.default_open_action = os.getenv('DEFAULT_OPEN_ACTION', 'auto')
        self.url_scheme = os.getenv('URL_SCHEME', 'https')
        self.logs_since = os.getenv('LOGS_SINCE', '10m')
        self.cache_ttl_ms = int(os.getenv('CACHE_TTL_MS', '2000'))
        self.fallback_shell = os.getenv('FALLBACK_SHELL', '/bin/sh')
        self.debug = os.getenv('DEBUG', '0') == '1'
        self.enable_stats = os.getenv('ENABLE_STATS', '0') == '1'
    
    def _load_env_file(self, env_file: Path):
        """Load environment variables from .env file"""
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        except Exception:
            pass  # Silently ignore .env file errors


class Cache:
    """Simple file-based cache with TTL"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / 'Library' / 'Caches' / 'com.yourdomain.orb-alfred'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config = Config()
    
    def get(self, key: str) -> Optional[Dict]:
        """Get cached data if not expired"""
        cache_file = self.cache_dir / f'{key}.json'
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            # Check if expired
            if time.time() * 1000 - data.get('timestamp', 0) > self.config.cache_ttl_ms:
                cache_file.unlink(missing_ok=True)
                return None
            
            return data.get('data')
        except Exception:
            cache_file.unlink(missing_ok=True)
            return None
    
    def set(self, key: str, data: Dict):
        """Cache data with current timestamp"""
        cache_file = self.cache_dir / f'{key}.json'
        
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': time.time() * 1000,
                    'data': data
                }, f)
        except Exception:
            pass  # Silently ignore cache write errors


class DockerClient:
    """Docker CLI wrapper with error handling and timeouts"""
    
    def __init__(self):
        self.config = Config()
        self.docker_path = self._find_docker_path()
    
    def _find_docker_path(self) -> Optional[str]:
        """Find docker binary in common locations"""
        paths = [
            '/usr/local/bin/docker',
            '/opt/homebrew/bin/docker',
            '/usr/bin/docker'
        ]
        
        for path in paths:
            if os.path.exists(path):
                return path
        
        # Try which command as fallback
        try:
            result = subprocess.run(['which', 'docker'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        return None
    
    def _run_command(self, cmd: List[str], timeout: float = 5.0) -> Tuple[bool, str, str]:
        """Run docker command with timeout and error handling"""
        if not self.docker_path:
            return False, '', 'Docker not found. Please ensure Docker/OrbStack is installed and in PATH.'
        
        full_cmd = [self.docker_path] + cmd
        
        try:
            if self.config.debug:
                self._debug_log(f"Running: {' '.join(full_cmd)}")
            
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if self.config.debug:
                self._debug_log(f"Exit code: {result.returncode}")
                if result.stdout:
                    self._debug_log(f"Stdout: {result.stdout[:200]}...")
                if result.stderr:
                    self._debug_log(f"Stderr: {result.stderr[:200]}...")
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, '', f'Docker command timed out after {timeout}s'
        except Exception as e:
            return False, '', f'Docker command failed: {str(e)}'
    
    def _debug_log(self, message: str):
        """Log debug message to file"""
        try:
            log_file = Path.home() / 'Library' / 'Logs' / 'orb-alfred.log'
            log_file.parent.mkdir(exist_ok=True)
            
            with open(log_file, 'a') as f:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                f.write(f'[{timestamp}] {message}\n')
        except Exception:
            pass
    
    def list_containers(self) -> List[Dict]:
        """Get all containers with basic info"""
        success, stdout, stderr = self._run_command([
            'ps', '--all', '--format', '{{json .}}'
        ])
        
        if not success:
            return []
        
        containers = []
        for line in stdout.strip().split('\n'):
            if line:
                try:
                    containers.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        return containers
    
    def inspect_containers(self, container_ids: List[str]) -> Dict[str, Dict]:
        """Batch inspect containers for detailed info"""
        if not container_ids:
            return {}
        
        success, stdout, stderr = self._run_command([
            'inspect', '--format', '{{json .}}'
        ] + container_ids, timeout=10.0)
        
        if not success:
            return {}
        
        inspected = {}
        for line in stdout.strip().split('\n'):
            if line:
                try:
                    data = json.loads(line)
                    inspected[data['Id']] = data
                except json.JSONDecodeError:
                    continue
        
        return inspected
    
    def get_stats(self, container_ids: List[str]) -> Dict[str, Dict]:
        """Get resource stats for containers"""
        if not container_ids:
            return {}
        
        success, stdout, stderr = self._run_command([
            'stats', '--no-stream', '--format',
            '{{.Container}} {{.CPUPerc}} {{.MemUsage}}'
        ] + container_ids, timeout=5.0)
        
        if not success:
            return {}
        
        stats = {}
        for line in stdout.strip().split('\n'):
            if line:
                parts = line.split(' ', 2)
                if len(parts) >= 3:
                    container_id = parts[0]
                    stats[container_id] = {
                        'cpu_percent': parts[1],
                        'memory_usage': parts[2]
                    }
        
        return stats


class URLDerivation:
    """URL derivation logic for orb.local domains"""
    
    def __init__(self):
        self.config = Config()

    def derive_url(self, container_data: Dict, inspect_data: Optional[Dict] = None) -> str:
        """Derive orb.local URL for container"""
        # Get project and service from labels
        project = None
        service = None
        
        if inspect_data and 'Config' in inspect_data and 'Labels' in inspect_data['Config']:
            labels = inspect_data['Config']['Labels'] or {}
            project = labels.get('com.docker.compose.project')
            service = labels.get('com.docker.compose.service')
        
        # Derive domain
        if project and service:
            domain = f"{service}.{project}.orb.local"
        else:
            # Use container name, clean it up
            container_name = container_data.get('Names', '').lstrip('/')
            if not container_name:
                container_name = container_data.get('ID', '')[:12]
            domain = f"{container_name}.orb.local"
        
        return f"{self.config.url_scheme}://{domain}/"
    
    def is_web_service(self, container_data: Dict, inspect_data: Optional[Dict] = None) -> bool:
        """Determine if container is likely a web service"""
        ports = self._extract_container_ports(container_data, inspect_data)

        if any(port in COMMON_WEB_PORTS for port in ports):
            return True

        # Check container/service name patterns
        if self._has_positive_name_hint(container_data, inspect_data):
            return True

        # Check image patterns
        image_lower = (container_data.get('Image') or '').lower()
        if any(keyword in image_lower for keyword in WEB_IMAGE_KEYWORDS):
            return True

        return False

    def _extract_container_ports(self, container_data: Dict, inspect_data: Optional[Dict]) -> List[int]:
        """Collect container ports from docker ps output and inspect data"""
        ports = set()

        def _add_port(value: Optional[str]):
            if not value:
                return
            value = value.strip()
            if not value:
                return
            port_part = value.split('/')[0]
            if port_part.isdigit():
                ports.add(int(port_part))

        ports_field = container_data.get('Ports', '')
        if ports_field:
            for mapping in ports_field.split(','):
                mapping = mapping.strip()
                if '->' in mapping:
                    target = mapping.split('->')[-1]
                    _add_port(target)
                else:
                    _add_port(mapping)

        inspect_data = inspect_data or {}
        config = inspect_data.get('Config', {})
        exposed_ports = config.get('ExposedPorts') or {}
        for port_key in exposed_ports.keys():
            _add_port(port_key)

        network_settings = inspect_data.get('NetworkSettings', {})
        network_ports = network_settings.get('Ports') or {}
        for port_key in network_ports.keys():
            _add_port(port_key)

        return sorted(ports)

    def _has_positive_name_hint(self, container_data: Dict, inspect_data: Optional[Dict]) -> bool:
        """Determine if names/labels indicate a web service"""
        candidates = []

        container_name = container_data.get('Names', '')
        if container_name:
            candidates.append(container_name.lstrip('/').lower())

        inspect_data = inspect_data or {}
        labels = (inspect_data.get('Config', {}) or {}).get('Labels') or {}
        service = labels.get('com.docker.compose.service', '')
        if service:
            candidates.append(service.lower())

        project = labels.get('com.docker.compose.project', '')
        if project:
            candidates.append(project.lower())

        for candidate in candidates:
            if any(neg in candidate for neg in NEGATIVE_SERVICE_KEYWORDS):
                continue
            if any(pos in candidate for pos in POSITIVE_SERVICE_KEYWORDS):
                return True

        return False


class ContainerManager:
    """High-level container management operations"""
    
    def __init__(self):
        self.docker = DockerClient()
        self.cache = Cache()
        self.url_derivation = URLDerivation()
        self.config = Config()
    
    def get_all_containers(self, use_cache: bool = True) -> List[Dict]:
        """Get enriched container data with caching"""
        cache_key = 'containers'
        
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        
        # Get basic container list
        containers = self.docker.list_containers()
        if not containers:
            return []
        
        # Get container IDs for batch inspect
        container_ids = [c.get('ID', '') for c in containers if c.get('ID')]
        
        # Batch inspect for detailed info
        inspect_data = self.docker.inspect_containers(container_ids)
        
        # Get stats (optional, can be slow)
        stats_data = {}
        if self.config.enable_stats:
            running_ids = [c.get('ID', '') for c in containers if 'Up' in c.get('Status', '')]
            try:
                stats_data = self.docker.get_stats(running_ids[:10])  # Limit to first 10 for performance
            except Exception:
                pass
        
        # Enrich container data
        enriched = []
        for container in containers:
            container_id = container.get('ID', '')
            
            # Find matching inspect data (short ID vs full ID)
            inspect_info = {}
            for full_id, data in inspect_data.items():
                if full_id.startswith(container_id):
                    inspect_info = data
                    break
            
            stats_info = stats_data.get(container_id, {})
            
            enriched_container = self._enrich_container(container, inspect_info, stats_info)
            enriched.append(enriched_container)
        
        # Sort: web services first, then running state, then by name
        enriched.sort(key=lambda c: (
            not c.get('is_web_service', False),
            c['status'] != 'running',
            c.get('display_name', '').lower()
        ))
        
        # Cache the results
        self.cache.set(cache_key, enriched)
        
        return enriched
    
    def _enrich_container(self, container: Dict, inspect_data: Dict, stats_data: Dict) -> Dict:
        """Enrich container with derived data"""
        # Basic info
        container_id = container.get('ID', '')
        container_name = container.get('Names', '').lstrip('/')
        
        # Extract labels
        labels = {}
        if inspect_data and 'Config' in inspect_data and 'Labels' in inspect_data['Config']:
            labels = inspect_data['Config']['Labels'] or {}
        
        project = labels.get('com.docker.compose.project')
        service = labels.get('com.docker.compose.service')
        
        # Health status
        health = 'unknown'
        if inspect_data and 'State' in inspect_data and 'Health' in inspect_data['State']:
            health = inspect_data['State']['Health'].get('Status', 'unknown')
        
        # Status
        status = container.get('Status', '').lower()
        if 'up' in status:
            status = 'running'
        elif 'exited' in status:
            status = 'stopped'
        else:
            status = 'unknown'
        
        # Display name (prefer service over container name)
        base_display_name = service or container_name or container_id[:12]
        
        # Derive URL and determine if the container is a web service
        url = self.url_derivation.derive_url(container, inspect_data)
        is_web = self.url_derivation.is_web_service(container, inspect_data)

        display_name = base_display_name
        if is_web:
            project_display = clean_project_name(project)
            if service and project_display:
                display_name = f"{service} - {project_display}"
            elif project_display:
                display_name = project_display
            elif service:
                display_name = service
        
        return {
            'id': container_id,
            'name': container_name,
            'display_name': display_name,
            'project': project,
            'service': service,
            'status': status,
            'health': health,
            'image': container.get('Image', ''),
            'ports': container.get('Ports', ''),
            'url': url,
            'is_web_service': is_web,
            'stats': stats_data,
            'labels': labels,
            'raw_container': container,
            'raw_inspect': inspect_data
        }
    
    def get_project_containers(self, project: str) -> List[Dict]:
        """Get all containers for a specific project"""
        all_containers = self.get_all_containers()
        return [c for c in all_containers if c.get('project') == project]


def format_subtitle(container: Dict) -> str:
    """Format subtitle for Alfred display"""
    parts = []
    
    # Project
    if container.get('project'):
        parts.append(container['project'])
    
    # Status
    status = container.get('status', 'unknown')
    if container.get('health') and container['health'] != 'unknown':
        status = f"{status} • {container['health']}"
    parts.append(status)

    # Web indicator and URL context
    if container.get('is_web_service'):
        url = container.get('url')
        if url:
            parts.append(f"🌐 {url.rstrip('/')}")

    # Stats
    stats = container.get('stats', {})
    if stats.get('cpu_percent'):
        parts.append(f"{stats['cpu_percent']} CPU")
    
    # Ports
    ports = container.get('ports', '')
    if ports and '->' in ports:
        # Extract just the port numbers for brevity
        port_parts = [p.strip() for p in ports.split(',')]
        if port_parts:
            parts.append(f"ports: {port_parts[0]}")
    
    return ' • '.join(parts)


def get_icon_path(status: str) -> str:
    """Get icon path based on container status"""
    if status == 'running':
        return 'icon.png'  # Green icon
    else:
        return 'icon-stopped.png'  # Grey icon
