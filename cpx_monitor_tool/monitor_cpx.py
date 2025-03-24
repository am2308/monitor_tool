#!/usr/bin/env python3

import argparse
import json
import requests
import time
from collections import defaultdict
from typing import Dict, List, Tuple
import sys
from datetime import datetime
import signal
from tabulate import tabulate  # Added tabulate import

class CPXMonitor:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.servers = []
        self.server_stats = {}
        self.last_update = None
        # Initialize servers immediately when creating the monitor
        self.fetch_servers()

    def fetch_servers(self) -> List[str]:
        """Fetch all servers from CPX API"""
        try:
            response = requests.get(f"{self.base_url}/servers", timeout=5)
            response.raise_for_status()
            self.servers = response.json()
            return self.servers
        except requests.exceptions.RequestException as e:
            print(f"Error fetching servers: {e}")
            return []

    def fetch_server_stats(self, ip: str) -> Dict:
        """Fetch stats for a specific server"""
        try:
            response = requests.get(f"{self.base_url}/{ip}", timeout=3)
            response.raise_for_status()
            stats = response.json()
            stats['ip'] = ip
            stats['status'] = 'Healthy' if int(stats['cpu'][:-1]) < 90 and int(stats['memory'][:-1]) < 90 else 'Unhealthy'
            return stats
        except requests.exceptions.RequestException as e:
            print(f"Error fetching stats for {ip}: {e}")
            return {}

    def update_all_stats(self):
        """Update stats for all servers"""
        self.server_stats = {}
        for ip in self.servers:
            stats = self.fetch_server_stats(ip)
            if stats:
                self.server_stats[ip] = stats
        self.last_update = datetime.now()

    def print_services_table(self):
        """Print all services in table format using tabulate"""
        if not self.servers:
            print("No servers found - please check CPX server connection")
            return
            
        self.update_all_stats()

        # Prepare data for tabulate
        table_data = []
        for ip, stats in self.server_stats.items():
            table_data.append([
                ip,
                stats['service'],
                stats['status'],
                stats['cpu'],
                stats['memory']
            ])

        headers = ["IP", "Service", "Status", "CPU", "Memory"]
        print("\nCurrent Services Status:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def show_service_averages(self):
        """Print average CPU/Memory using tabulate"""
        if not self.servers:
            print("No servers found - please check CPX server connection")
            return
            
        self.update_all_stats()

        service_data = defaultdict(lambda: {'cpu_total': 0, 'memory_total': 0, 'count': 0})
        
        for stats in self.server_stats.values():
            service = stats['service']
            cpu = int(stats['cpu'][:-1])
            memory = int(stats['memory'][:-1])
            
            service_data[service]['cpu_total'] += cpu
            service_data[service]['memory_total'] += memory
            service_data[service]['count'] += 1

        # Prepare data for tabulate
        table_data = []
        for service, data in service_data.items():
            avg_cpu = data['cpu_total'] / data['count']
            avg_memory = data['memory_total'] / data['count']
            table_data.append([
                service,
                f"{avg_cpu:.1f}%",
                f"{avg_memory:.1f}%"
            ])

        headers = ["Service", "Avg CPU", "Avg Memory"]
        print("\nService Averages:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def flag_underprovisioned_services(self):
        """Flag services with fewer than 2 healthy instances using tabulate"""
        if not self.servers:
            print("No servers found - please check CPX server connection")
            return
            
        self.update_all_stats()

        healthy_counts = defaultdict(int)
        service_instances = defaultdict(list)
        
        for stats in self.server_stats.values():
            service = stats['service']
            if stats['status'] == 'Healthy':
                healthy_counts[service] += 1
            service_instances[service].append(stats)

        # Prepare data for tabulate
        table_data = []
        for service, count in healthy_counts.items():
            if count < 2:
                instances = service_instances[service]
                for instance in instances:
                    table_data.append([
                        service,
                        instance['ip'],
                        instance['status'],
                        instance['cpu'],
                        instance['memory'],
                        f"Only {count} healthy" if count < 2 else "OK"
                    ])

        if table_data:
            headers = ["Service", "IP", "Status", "CPU", "Memory", "Health Status"]
            print("\n Underprovisioned Services (fewer than 2 healthy instances):")
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("\n All services have at least 2 healthy instances")

    def track_service(self, service_name: str):
        """Monitor a specific service over time with tabulate"""
        if not self.servers:
            print("No servers found - please check CPX server connection")
            return
            
        print(f"\n Monitoring {service_name} (press Ctrl+C to stop)...\n")
        
        def signal_handler(sig, frame):
            print("\n Monitoring stopped")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)

        try:
            while True:
                self.update_all_stats()
                service_instances = [stats for stats in self.server_stats.values() 
                                   if stats['service'] == service_name]
                
                if not service_instances:
                    print(f"No instances found for service: {service_name}")
                    break
                
                # Prepare data for tabulate
                table_data = []
                for stats in service_instances:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    table_data.append([
                        timestamp,
                        stats['ip'],
                        stats['status'],
                        stats['cpu'],
                        stats['memory']
                    ])

                headers = ["Timestamp", "IP", "Status", "CPU", "Memory"]
                print(tabulate(table_data, headers=headers, tablefmt="grid"))
                print()  # Add space between updates
                
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n Monitoring stopped")

def main():
    parser = argparse.ArgumentParser(description="CPX Monitoring Tool")
    parser.add_argument("--port", type=int, default=8000, help="Port of CPX server")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command 1: List services
    list_parser = subparsers.add_parser("list", help="List all services")

    # Command 2: Show averages
    avg_parser = subparsers.add_parser("averages", help="Show service averages")

    # Command 3: Flag underprovisioned
    flag_parser = subparsers.add_parser("flag", help="Flag underprovisioned services")

    # Command 4: Monitor service
    monitor_parser = subparsers.add_parser("track", help="Monitor a specific service")
    monitor_parser.add_argument("--service", help="Service name to monitor")

    args = parser.parse_args()

    monitor = CPXMonitor(f"http://localhost:{args.port}")

    if args.command == "list":
        monitor.print_services_table()
    elif args.command == "averages":
        monitor.show_service_averages()
    elif args.command == "flag":
        monitor.flag_underprovisioned_services()
    elif args.command == "track":
        monitor.track_service(args.service)

if __name__ == "__main__":
    main()
