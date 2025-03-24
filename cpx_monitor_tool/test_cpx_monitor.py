#!/usr/bin/env python3

import unittest
from unittest.mock import patch, MagicMock
from monitor_cpx import CPXMonitor
import requests

class TestCPXMonitor(unittest.TestCase):
    def setUp(self):
        # Patch the fetch_servers method to return empty list initially
        with patch.object(CPXMonitor, 'fetch_servers', return_value=[]):
            self.monitor = CPXMonitor("http://localhost:5008")

    @patch('requests.get')
    def test_fetch_servers(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = ["10.58.1.1", "10.58.1.2"]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        servers = self.monitor.fetch_servers()
        self.assertEqual(servers, ["10.58.1.1", "10.58.1.2"])

    @patch('requests.get')
    def test_fetch_server_stats(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "cpu": "50%",
            "memory": "30%",
            "service": "AuthService"
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        stats = self.monitor.fetch_server_stats("10.58.1.1")
        self.assertEqual(stats["service"], "AuthService")
        self.assertEqual(stats["status"], "Healthy")

    def test_update_all_stats(self):
        # Setup mock return values directly on the instance
        self.monitor.servers = ["10.58.1.1", "10.58.1.2"]
        
        # Mock the fetch_server_stats method
        with patch.object(self.monitor, 'fetch_server_stats') as mock_fetch_stats:
            mock_fetch_stats.side_effect = [
                {  # First call
                    "ip": "10.58.1.1",
                    "cpu": "50%",
                    "memory": "30%",
                    "service": "AuthService",
                    "status": "Healthy"
                },
                {  # Second call
                    "ip": "10.58.1.2",
                    "cpu": "60%",
                    "memory": "40%",
                    "service": "UserService",
                    "status": "Healthy"
                }
            ]

            # Execute the test
            self.monitor.update_all_stats()
            
            # Verify results
            self.assertEqual(len(self.monitor.server_stats), 2)
            self.assertEqual(self.monitor.server_stats["10.58.1.1"]["service"], "AuthService")
            self.assertEqual(self.monitor.server_stats["10.58.1.2"]["service"], "UserService")
        
    @patch('requests.get')
    def test_empty_server_response(self, mock_get):
        mock_get.return_value.json.return_value = []
        servers = self.monitor.fetch_servers()
        self.assertEqual(servers, [])

    @patch('requests.get')
    def test_server_stats_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()
        stats = self.monitor.fetch_server_stats("10.58.1.1")
        self.assertEqual(stats, {})

if __name__ == '__main__':
    unittest.main()