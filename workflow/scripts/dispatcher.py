#!/usr/bin/env python3
"""
Alfred Action Dispatcher for OrbStack Container Management
Handles all container actions triggered from Alfred
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Add the scripts directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from helpers import ContainerManager, DockerClient, Config


class ActionDispatcher:
    """Handles all container actions"""
    
    def __init__(self):
        self.docker = DockerClient()
        self.config = Config()
        self.manager = ContainerManager()
    
    def run_action(self, action_data: dict):
        """Dispatch action based on action_data"""
        action = action_data.get('action')
        
        if action == 'default':
            self._handle_default_action(action_data)
        elif action == 'open_url':
            self._open_url(action_data.get('url'))
        elif action == 'start':
            self._start_container(action_data.get('id'))
        elif action == 'stop':
            self._stop_container(action_data.get('id'))
        elif action == 'restart':
            self._restart_container(action_data.get('id'))
        elif action == 'logs':
            self._show_logs(action_data.get('id'), action_data.get('name'))
        elif action == 'shell':
            self._open_shell(action_data.get('id'), action_data.get('name'))
        elif action == 'copy_url':
            self._copy_url(action_data.get('url'))
        elif action == 'project_action':
            self._handle_project_action(action_data)
        else:
            self._show_error(f"Unknown action: {action}")
    
    def _handle_default_action(self, action_data: dict):
        """Handle default Enter action based on heuristics"""
        default_action = action_data.get('default_action', 'shell')
        
        if default_action == 'open_url':
            self._open_url(action_data.get('url'))
        else:
            self._open_shell(action_data.get('id'), action_data.get('name'))
    
    def _open_url(self, url: str):
        """Open URL in default browser"""
        if not url:
            self._show_error("No URL provided")
            return
        
        try:
            subprocess.run(['open', url], check=True)
            self._show_notification(f"Opened {url}")
        except subprocess.CalledProcessError:
            self._show_error(f"Failed to open {url}")
    
    def _start_container(self, container_id: str):
        """Start a container"""
        if not container_id:
            self._show_error("No container ID provided")
            return
        
        success, stdout, stderr = self.docker._run_command(['start', container_id])
        
        if success:
            self._show_notification(f"Started container {container_id[:12]}")
            # Clear cache to reflect new state
            self._clear_cache()
        else:
            self._show_error(f"Failed to start container: {stderr}")
    
    def _stop_container(self, container_id: str):
        """Stop a container"""
        if not container_id:
            self._show_error("No container ID provided")
            return
        
        success, stdout, stderr = self.docker._run_command(['stop', container_id])
        
        if success:
            self._show_notification(f"Stopped container {container_id[:12]}")
            # Clear cache to reflect new state
            self._clear_cache()
        else:
            self._show_error(f"Failed to stop container: {stderr}")
    
    def _restart_container(self, container_id: str):
        """Restart a container"""
        if not container_id:
            self._show_error("No container ID provided")
            return
        
        success, stdout, stderr = self.docker._run_command(['restart', container_id])
        
        if success:
            self._show_notification(f"Restarted container {container_id[:12]}")
            # Clear cache to reflect new state
            self._clear_cache()
        else:
            self._show_error(f"Failed to restart container: {stderr}")
    
    def _show_logs(self, container_id: str, container_name: str = None):
        """Show container logs in terminal"""
        if not container_id:
            self._show_error("No container ID provided")
            return
        
        display_name = container_name or container_id[:12]
        
        # Create terminal command
        docker_path = self.docker.docker_path
        if not docker_path:
            self._show_error("Docker not found")
            return
        
        cmd = f'"{docker_path}" logs --since={self.config.logs_since} --tail=200 -f {container_id}'
        title = f"Logs: {display_name}"
        
        # Open in Terminal
        terminal_script = f'''
        tell application "Terminal"
            activate
            do script "{cmd}"
            set custom title of front window to "{title}"
        end tell
        '''
        
        try:
            subprocess.run(['osascript', '-e', terminal_script], check=True)
        except subprocess.CalledProcessError:
            self._show_error("Failed to open terminal")
    
    def _open_shell(self, container_id: str, container_name: str = None):
        """Open interactive shell in container"""
        if not container_id:
            self._show_error("No container ID provided")
            return
        
        display_name = container_name or container_id[:12]
        
        # Check if container is running
        success, stdout, stderr = self.docker._run_command(['inspect', '-f', '{{.State.Running}}', container_id])
        
        if not success or stdout.strip() != 'true':
            self._show_error("Container is not running")
            return
        
        # Try different shells
        docker_path = self.docker.docker_path
        if not docker_path:
            self._show_error("Docker not found")
            return
        
        shells = ['/bin/bash', '/bin/sh', '/bin/zsh']
        
        for shell in shells:
            # Test if shell exists in container
            test_success, _, _ = self.docker._run_command([
                'exec', container_id, 'test', '-f', shell
            ])
            
            if test_success:
                # Found working shell
                cmd = f'"{docker_path}" exec -it {container_id} {shell}'
                title = f"Shell: {display_name}"
                
                # Open in Terminal
                terminal_script = f'''
                tell application "Terminal"
                    activate
                    do script "{cmd}"
                    set custom title of front window to "{title}"
                end tell
                '''
                
                try:
                    subprocess.run(['osascript', '-e', terminal_script], check=True)
                    return
                except subprocess.CalledProcessError:
                    self._show_error("Failed to open terminal")
                    return
        
        # No shell found
        self._show_error("No suitable shell found in container")
    
    def _copy_url(self, url: str):
        """Copy URL to clipboard"""
        if not url:
            self._show_error("No URL provided")
            return
        
        try:
            subprocess.run(['pbcopy'], input=url.encode(), check=True)
            self._show_notification(f"Copied {url}")
        except subprocess.CalledProcessError:
            self._show_error("Failed to copy URL")
    
    def _handle_project_action(self, action_data: dict):
        """Handle project-level batch actions"""
        project = action_data.get('project')
        action_type = action_data.get('project_action', '')
        
        if not project:
            self._show_error("No project specified")
            return
        
        # Get project containers
        project_containers = self.manager.get_project_containers(project)
        
        if not project_containers:
            self._show_error(f"No containers found for project {project}")
            return
        
        container_ids = [c['id'] for c in project_containers]
        
        if action_type == 'start_project':
            # Start all stopped containers
            stopped_ids = [c['id'] for c in project_containers if c['status'] != 'running']
            if stopped_ids:
                self._batch_action('start', stopped_ids, f"project {project}")
            else:
                self._show_notification(f"All containers in {project} are already running")
        
        elif action_type == 'stop_project':
            # Stop all running containers
            running_ids = [c['id'] for c in project_containers if c['status'] == 'running']
            if running_ids:
                self._batch_action('stop', running_ids, f"project {project}")
            else:
                self._show_notification(f"All containers in {project} are already stopped")
        
        else:
            self._show_error(f"Unknown project action: {action_type}")
    
    def _batch_action(self, action: str, container_ids: list, description: str):
        """Perform batch action on multiple containers"""
        success_count = 0
        
        for container_id in container_ids:
            success, stdout, stderr = self.docker._run_command([action, container_id])
            if success:
                success_count += 1
        
        if success_count == len(container_ids):
            self._show_notification(f"Successfully {action}ed {success_count} containers in {description}")
        elif success_count > 0:
            self._show_notification(f"{action.title()}ed {success_count}/{len(container_ids)} containers in {description}")
        else:
            self._show_error(f"Failed to {action} containers in {description}")
        
        # Clear cache to reflect new state
        self._clear_cache()
    
    def _clear_cache(self):
        """Clear container cache"""
        try:
            cache_file = self.manager.cache.cache_dir / 'containers.json'
            cache_file.unlink(missing_ok=True)
        except Exception:
            pass
    
    def _show_notification(self, message: str):
        """Show macOS notification"""
        try:
            subprocess.run([
                'osascript', '-e',
                f'display notification "{message}" with title "OrbStack Alfred"'
            ], check=True)
        except subprocess.CalledProcessError:
            # Fallback to Large Type
            self._show_large_type(message)
    
    def _show_error(self, message: str):
        """Show error message"""
        try:
            subprocess.run([
                'osascript', '-e',
                f'display notification "{message}" with title "OrbStack Alfred Error"'
            ], check=True)
        except subprocess.CalledProcessError:
            # Fallback to Large Type
            self._show_large_type(f"Error: {message}")
    
    def _show_large_type(self, message: str):
        """Show Large Type display"""
        try:
            subprocess.run([
                'osascript', '-e',
                f'tell application "Alfred" to show large type "{message}"'
            ], check=True)
        except subprocess.CalledProcessError:
            # Final fallback - print to stderr
            print(f"Error: {message}", file=sys.stderr)


def main():
    """Main dispatcher entry point"""
    try:
        # Debug: Log what we receive from Alfred
        import os
        debug_log = f"/tmp/alfred_dispatcher_debug_{os.getpid()}.log"
        with open(debug_log, 'w') as f:
            f.write(f"Raw dispatcher args: {sys.argv}\n")
        
        # Get action data from Alfred
        if len(sys.argv) < 2:
            print("No action data provided", file=sys.stderr)
            sys.exit(1)
        
        action_json = sys.argv[1]
        
        with open(debug_log, 'a') as f:
            f.write(f"Original JSON: {repr(action_json)}\n")
        
        # Handle Alfred's special JSON format (without quotes around keys)
        if action_json.startswith('{') and not action_json.startswith('{"'):
            # Parse manually since Alfred strips quotes
            action_data = {}
            # Remove braces and split by commas
            content = action_json.strip('{}')
            pairs = [pair.strip() for pair in content.split(',')]
            
            for pair in pairs:
                if ':' in pair:
                    key, value = pair.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Handle null values
                    if value == 'null':
                        value = None
                    # Handle boolean values
                    elif value == 'true':
                        value = True
                    elif value == 'false':
                        value = False
                    # Everything else is a string
                    else:
                        value = str(value)
                    
                    action_data[key] = value
        else:
            # Standard JSON parsing
            action_data = json.loads(action_json)
        
        with open(debug_log, 'a') as f:
            f.write(f"Parsed data: {action_data}\n")
        
        # Execute action
        dispatcher = ActionDispatcher()
        dispatcher.run_action(action_data)
    
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Action failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()