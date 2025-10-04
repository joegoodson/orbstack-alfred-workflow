#!/usr/bin/env python3
"""
Test container parsing and enrichment for OrbStack Alfred Workflow
"""

import json
import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add the scripts directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'workflow' / 'scripts'))

from helpers import ContainerManager, format_subtitle
from script_filter import create_container_item, create_project_item


class TestContainerParsing(unittest.TestCase):
    
    def setUp(self):
        # Load test fixtures
        fixtures_dir = Path(__file__).parent / 'fixtures'
        
        with open(fixtures_dir / 'docker_ps_all.jsonl', 'r') as f:
            self.ps_data = [json.loads(line) for line in f if line.strip()]
        
        with open(fixtures_dir / 'docker_inspect_all.json', 'r') as f:
            self.inspect_data = json.load(f)
    
    def test_enrich_compose_container(self):
        """Test enrichment of Compose container"""
        manager = ContainerManager()
        
        container = self.ps_data[0]  # 0089-dramdeals-web
        inspect_info = self.inspect_data[0]
        stats_info = {'cpu_percent': '0.5%', 'memory_usage': '50MiB / 1GiB'}
        
        enriched = manager._enrich_container(container, inspect_info, stats_info)
        
        self.assertEqual(enriched['id'], '4f3c2d1e90a1')
        self.assertEqual(enriched['name'], '0089-dramdeals-web')
        self.assertEqual(enriched['display_name'], 'web - dramdeals')
        self.assertEqual(enriched['project'], '0089-dramdeals')
        self.assertEqual(enriched['service'], 'web')
        self.assertEqual(enriched['status'], 'running')
        self.assertEqual(enriched['health'], 'healthy')
        self.assertEqual(enriched['url'], 'https://web.0089-dramdeals.orb.local/')
        self.assertTrue(enriched['is_web_service'])

    def test_enrich_standalone_container(self):
        """Test enrichment of standalone container"""
        manager = ContainerManager()
        
        container = self.ps_data[2]  # standalone-redis
        inspect_info = self.inspect_data[2]
        stats_info = {}
        
        enriched = manager._enrich_container(container, inspect_info, stats_info)
        
        self.assertEqual(enriched['id'], '1f2a3b4c5d6e')
        self.assertEqual(enriched['name'], 'standalone-redis')
        self.assertEqual(enriched['display_name'], 'standalone-redis')
        self.assertIsNone(enriched['project'])
        self.assertIsNone(enriched['service'])
        self.assertEqual(enriched['status'], 'stopped')
        self.assertEqual(enriched['url'], 'https://standalone-redis.orb.local/')
        self.assertFalse(enriched['is_web_service'])
    
    def test_enrich_unhealthy_container(self):
        """Test enrichment of unhealthy container"""
        manager = ContainerManager()
        
        container = self.ps_data[4]  # unhealthy-service
        inspect_info = self.inspect_data[4]
        stats_info = {}
        
        enriched = manager._enrich_container(container, inspect_info, stats_info)
        
        self.assertEqual(enriched['health'], 'unhealthy')
        self.assertEqual(enriched['status'], 'running')
        self.assertTrue(enriched['is_web_service'])

    def test_database_service_not_marked_web(self):
        """Ensure database-like services are not treated as web"""
        manager = ContainerManager()

        container = self.ps_data[1]  # 0089-dramdeals-web_db
        inspect_info = self.inspect_data[1]
        stats_info = {}

        enriched = manager._enrich_container(container, inspect_info, stats_info)

        self.assertEqual(enriched['display_name'], 'web_db')
        self.assertFalse(enriched['is_web_service'])
    
    def test_format_subtitle_with_project(self):
        """Test subtitle formatting with project"""
        container = {
            'project': '0089-dramdeals',
            'status': 'running',
            'health': 'healthy',
            'stats': {'cpu_percent': '0.5%'},
            'ports': '0.0.0.0:8080->80/tcp'
        }
        
        subtitle = format_subtitle(container)
        expected_parts = ['0089-dramdeals', 'running • healthy', '0.5% CPU', 'ports: 0.0.0.0:8080->80/tcp']
        
        for part in expected_parts:
            self.assertIn(part, subtitle)
    
    def test_format_subtitle_without_project(self):
        """Test subtitle formatting without project"""
        container = {
            'status': 'stopped',
            'health': 'unknown',
            'stats': {},
            'ports': ''
        }
        
        subtitle = format_subtitle(container)
        self.assertIn('stopped', subtitle)
        self.assertNotIn('unknown', subtitle)  # Health should be filtered out if unknown
    
    def test_format_subtitle_minimal(self):
        """Test subtitle formatting with minimal data"""
        container = {
            'status': 'running'
        }
        
        subtitle = format_subtitle(container)
        self.assertEqual(subtitle, 'running')

    def test_web_container_title_includes_status_emoji(self):
        container = {
            'id': 'abc123',
            'name': '0089-dramdeals-web',
            'display_name': 'web - dramdeals',
            'project': '0089-dramdeals',
            'service': 'web',
            'status': 'running',
            'health': 'healthy',
            'url': 'https://web.0089-dramdeals.orb.local/',
            'is_web_service': True,
            'stats': {},
            'ports': ''
        }

        item = create_container_item(container)
        self.assertEqual(item['title'], '🌐 web - dramdeals ✅')

    def test_stopped_container_title_uses_stop_emoji(self):
        container = {
            'id': 'def456',
            'name': 'worker',
            'display_name': 'worker',
            'project': None,
            'service': None,
            'status': 'stopped',
            'health': 'unknown',
            'url': 'https://worker.orb.local/',
            'is_web_service': False,
            'stats': {},
            'ports': ''
        }

        item = create_container_item(container)
        self.assertTrue(item['title'].endswith('🛑'))
        self.assertNotIn('🌐', item['title'])

    def test_project_item_title_emojis(self):
        containers = [
            {
                'id': '1',
                'name': 'service',
                'display_name': 'service',
                'project': 'demo',
                'service': 'service',
                'status': 'running',
                'health': 'healthy',
                'url': 'https://service.demo.orb.local/',
                'is_web_service': True,
                'stats': {},
                'ports': ''
            }
        ]

        running_item = create_project_item('demo', containers)
        self.assertTrue(running_item['title'].endswith('✅'))

        for c in containers:
            c['status'] = 'stopped'
        stopped_item = create_project_item('demo', containers)
        self.assertTrue(stopped_item['title'].endswith('🛑'))


if __name__ == '__main__':
    unittest.main()
