#!/usr/bin/env python3
"""
Test URL derivation logic for OrbStack Alfred Workflow
"""

import unittest
import sys
from pathlib import Path

# Add the scripts directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'workflow' / 'scripts'))

from helpers import URLDerivation


class TestURLDerivation(unittest.TestCase):
    
    def setUp(self):
        self.url_derivation = URLDerivation()
    
    def test_compose_service_url(self):
        """Test URL derivation for Compose services"""
        container_data = {
            'Names': '/0089-dramdeals-web',
            'Ports': '0.0.0.0:8080->80/tcp'
        }
        
        inspect_data = {
            'Config': {
                'Labels': {
                    'com.docker.compose.project': '0089-dramdeals',
                    'com.docker.compose.service': 'web'
                }
            }
        }
        
        url = self.url_derivation.derive_url(container_data, inspect_data)
        self.assertEqual(url, 'https://web.0089-dramdeals.orb.local/')
    
    def test_standalone_container_url(self):
        """Test URL derivation for standalone containers"""
        container_data = {
            'Names': '/standalone-redis',
            'Ports': ''
        }
        
        inspect_data = {
            'Config': {
                'Labels': None
            }
        }
        
        url = self.url_derivation.derive_url(container_data, inspect_data)
        self.assertEqual(url, 'https://standalone-redis.orb.local/')
    
    def test_container_without_name(self):
        """Test URL derivation for container without name"""
        container_data = {
            'Names': '',
            'ID': '4f3c2d1e90a1',
            'Ports': ''
        }
        
        inspect_data = {
            'Config': {
                'Labels': None
            }
        }
        
        url = self.url_derivation.derive_url(container_data, inspect_data)
        self.assertEqual(url, 'https://4f3c2d1e90a1.orb.local/')
    
    def test_web_service_detection_by_ports(self):
        """Test web service detection by exposed ports"""
        container_data = {
            'Names': '/test-app',
            'Ports': '0.0.0.0:8080->80/tcp'
        }
        
        is_web = self.url_derivation.is_web_service(container_data)
        self.assertTrue(is_web)
    
    def test_web_service_detection_by_port_443(self):
        """Test web service detection by HTTPS port"""
        container_data = {
            'Names': '/test-app',
            'Ports': '0.0.0.0:8443->443/tcp'
        }
        
        is_web = self.url_derivation.is_web_service(container_data)
        self.assertTrue(is_web)
    
    def test_web_service_detection_by_name(self):
        """Test web service detection by container name"""
        container_data = {
            'Names': '/my-web-app',
            'Ports': ''
        }
        
        is_web = self.url_derivation.is_web_service(container_data)
        self.assertTrue(is_web)
    
    def test_web_service_detection_by_image(self):
        """Test web service detection by image name"""
        container_data = {
            'Names': '/test-container',
            'Ports': '',
            'Image': 'nginx:alpine'
        }
        
        is_web = self.url_derivation.is_web_service(container_data)
        self.assertTrue(is_web)
    
    def test_web_service_detection_by_service_label(self):
        """Test web service detection by service label"""
        container_data = {
            'Names': '/test-container',
            'Ports': ''
        }
        
        inspect_data = {
            'Config': {
                'Labels': {
                    'com.docker.compose.service': 'frontend'
                }
            }
        }
        
        is_web = self.url_derivation.is_web_service(container_data, inspect_data)
        self.assertTrue(is_web)
    
    def test_non_web_service_detection(self):
        """Test non-web service detection"""
        container_data = {
            'Names': '/redis-cache',
            'Ports': '',
            'Image': 'redis:7'
        }
        
        inspect_data = {
            'Config': {
                'Labels': {
                    'com.docker.compose.service': 'cache'
                }
            }
        }

        is_web = self.url_derivation.is_web_service(container_data, inspect_data)
        self.assertFalse(is_web)

    def test_database_not_detected_as_web(self):
        """Ensure containers with database-style names are excluded"""
        container_data = {
            'Names': '/0089-dramdeals-web_db',
            'Ports': '',
            'Image': 'postgres:15'
        }

        inspect_data = {
            'Config': {
                'Labels': {
                    'com.docker.compose.project': '0089-dramdeals',
                    'com.docker.compose.service': 'web_db'
                }
            }
        }

        is_web = self.url_derivation.is_web_service(container_data, inspect_data)
        self.assertFalse(is_web)


if __name__ == '__main__':
    unittest.main()
