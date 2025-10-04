#!/usr/bin/env python3
"""
Alfred Script Filter for OrbStack Container Management
Lists containers with actions and modifiers
"""

import json
import sys
from pathlib import Path

# Add the scripts directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from helpers import ContainerManager, format_subtitle, get_icon_path


def create_action_arg(action: str, container: dict, **kwargs) -> str:
    """Create JSON argument for actions"""
    arg_data = {
        'action': action,
        'id': container['id'],
        'name': container['name'],
        'project': container.get('project'),
        'service': container.get('service'),
        'url': container['url'],
        **kwargs
    }
    return json.dumps(arg_data)


def create_container_item(container: dict) -> dict:
    """Create Alfred item for a container"""
    # Determine default action based on heuristics
    default_action = 'open_url' if container['is_web_service'] else 'shell'
    
    # Base item
    title = container['display_name']
    if container.get('is_web_service'):
        title = f"🌐 {title}"

    item = {
        'uid': container['id'],
        'title': title,
        'subtitle': format_subtitle(container),
        'arg': create_action_arg('default', container, default_action=default_action),
        'autocomplete': container['display_name'],
        'valid': True,
        'icon': {
            'path': get_icon_path(container['status'])
        },
        'mods': {}
    }
    
    # Cmd modifier - Always open URL
    item['mods']['cmd'] = {
        'subtitle': f"Open {container['url']}",
        'arg': create_action_arg('open_url', container)
    }
    
    # Alt modifier - Toggle start/stop
    if container['status'] == 'running':
        item['mods']['alt'] = {
            'subtitle': 'Stop container',
            'arg': create_action_arg('stop', container)
        }
    else:
        item['mods']['alt'] = {
            'subtitle': 'Start container',
            'arg': create_action_arg('start', container)
        }
    
    # Ctrl modifier - Show logs
    item['mods']['ctrl'] = {
        'subtitle': 'Tail logs',
        'arg': create_action_arg('logs', container)
    }
    
    # Shift modifier - Copy URL
    item['mods']['shift'] = {
        'subtitle': f"Copy {container['url']}",
        'arg': create_action_arg('copy_url', container)
    }
    
    return item


def create_project_item(project: str, containers: list) -> dict:
    """Create Alfred item for project batch actions"""
    running_count = sum(1 for c in containers if c['status'] == 'running')
    stopped_count = len(containers) - running_count
    
    if running_count > 0:
        action = 'stop_project'
        subtitle = f"Stop {running_count} running containers"
    else:
        action = 'start_project'
        subtitle = f"Start {stopped_count} stopped containers"
    
    return {
        'uid': f'project_{project}',
        'title': f"📦 {project}",
        'subtitle': f"{subtitle} • {len(containers)} total containers",
        'arg': create_action_arg('project_action', {'id': project, 'name': project, 'url': ''}, project_action=action, project=project),
        'autocomplete': f"project {project}",
        'valid': True,
        'icon': {
            'path': 'icon.png'
        }
    }


def create_error_item(title: str, subtitle: str) -> dict:
    """Create Alfred item for errors"""
    return {
        'uid': 'error',
        'title': title,
        'subtitle': subtitle,
        'valid': False,
        'icon': {
            'path': 'icon.png'
        }
    }


def create_empty_item() -> dict:
    """Create Alfred item for empty state"""
    return {
        'uid': 'empty',
        'title': 'No containers found',
        'subtitle': 'No Docker containers are available. Try starting some containers in OrbStack.',
        'valid': False,
        'icon': {
            'path': 'icon.png'
        }
    }


def filter_containers(containers: list, query: str) -> list:
    """Filter containers based on query"""
    if not query:
        return containers
    
    query_lower = query.lower()
    filtered = []
    
    for container in containers:
        # Search in display name, container name, project, service
        searchable_fields = [
            container.get('display_name', ''),
            container.get('name', ''),
            container.get('project', ''),
            container.get('service', ''),
            container.get('image', '')
        ]
        
        if any(query_lower in str(field).lower() for field in searchable_fields if field):
            filtered.append(container)
    
    return filtered


def main():
    """Main script filter entry point"""
    try:
        # Get query from Alfred
        query = sys.argv[1] if len(sys.argv) > 1 else ''
        
        # Debug: Log what we receive from Alfred
        import os
        debug_log = f"/tmp/alfred_debug_{os.getpid()}.log"
        with open(debug_log, 'w') as f:
            f.write(f"Raw args: {sys.argv}\n")
            f.write(f"Query received: '{query}'\n")
        
        # Debug: Handle literal {query} string passed by Alfred
        if query == '{query}':
            query = ''
        
        # Initialize container manager
        manager = ContainerManager()
        
        # Check if Docker is available
        if not manager.docker.docker_path:
            items = [create_error_item(
                'Docker not found',
                'Please ensure Docker/OrbStack is installed and in PATH'
            )]
        else:
            # Get all containers
            containers = manager.get_all_containers()
            
            if not containers:
                items = [create_empty_item()]
            else:
                # Filter containers based on query
                filtered_containers = filter_containers(containers, query)
                
                if not filtered_containers:
                    items = [create_error_item(
                        'No matching containers',
                        f'No containers match "{query}"'
                    )]
                else:
                    items = []
                    
                    container_items = [create_container_item(container) for container in filtered_containers]

                    # Group by project for batch actions (add after container list)
                    projects = {}
                    for container in filtered_containers:
                        project = container.get('project')
                        if project:
                            projects.setdefault(project, []).append(container)

                    project_items = [
                        create_project_item(project, project_containers)
                        for project, project_containers in projects.items()
                        if len(project_containers) > 1
                    ]

                    items.extend(container_items)
                    items.extend(project_items)
        
        # Output Alfred JSON
        result = {'items': items}
        print(json.dumps(result, indent=2))
    
    except Exception as e:
        # Error fallback with more debugging
        import traceback
        error_detail = traceback.format_exc()
        
        # Log error for debugging
        try:
            import os
            debug_log = f"/tmp/alfred_script_error_{os.getpid()}.log"
            with open(debug_log, 'w') as f:
                f.write(f"Script filter error: {str(e)}\n")
                f.write(f"Traceback:\n{error_detail}\n")
        except:
            pass
        
        error_item = create_error_item(
            'Workflow error',
            f'An error occurred: {str(e)}'
        )
        result = {'items': [error_item]}
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
