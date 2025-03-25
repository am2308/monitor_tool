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
from tabulate import tabulate
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler

### CPX Dashboard library imports
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
import time



# Load environment variables
load_dotenv()

# Configure logging
def setup_logging():
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_file = 'cpx_monitor.log'
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            RotatingFileHandler(
                filename=f'logs/{log_file}',
                maxBytes=5*1024*1024,  # 5MB
                backupCount=3
            ),
            #logging.StreamHandler()
        ]
    )
    
    # Set lower level for more verbose logging if needed
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    return logging.getLogger(__name__)

logger = setup_logging()

### CPX Dashboard
class TerminalDashboard:
    def __init__(self, monitor):
        self.monitor = monitor
        self.console = Console()
        logger.info("Dashboard initialized")

    def _refresh_data(self):
        """Force update monitor data"""
        try:
            self.monitor.update_all_stats()
            return True
        except Exception as e:
            logger.error(f"Data refresh failed: {e}")
            return False

    def _create_stats_table(self):
        """Generate service stats table"""
        table = Table(title="Service Status")
        table.add_column("Service")
        table.add_column("Healthy", justify="right")
        table.add_column("Avg CPU", justify="right")
        table.add_column("Avg Memory", justify="right")
        
        if not self.monitor.server_stats:
            table.add_row("[red]No data available[/]", "", "", "")
            return table
            
        service_data = defaultdict(lambda: {'healthy': 0, 'cpu': 0, 'memory': 0, 'total': 0})
        
        for stats in self.monitor.server_stats.values():
            service = stats['service']
            service_data[service]['cpu'] += int(stats['cpu'][:-1])
            service_data[service]['memory'] += int(stats['memory'][:-1])
            service_data[service]['total'] += 1
            if stats['status'] == 'Healthy':
                service_data[service]['healthy'] += 1
        
        for service, data in service_data.items():
            healthy_pct = (data['healthy'] / data['total']) * 100
            table.add_row(
                service,
                f"[green]{data['healthy']}/{data['total']}[/]" if healthy_pct > 75 else 
                f"[yellow]{data['healthy']}/{data['total']}[/]" if healthy_pct > 50 else 
                f"[red]{data['healthy']}/{data['total']}[/]",
                f"{data['cpu']/data['total']:.1f}%",
                f"{data['memory']/data['total']:.1f}%"
            )
            
        return table

    def _create_alerts_panel(self):
        """Generate alerts panel"""
        if not self.monitor.server_stats:
            return Panel("[yellow]Waiting for first data update...[/]", style="yellow")
            
        alerts = []
        for ip, stats in self.monitor.server_stats.items():
            if stats['status'] == 'Unhealthy':
                alerts.append(
                    f"[red]• {stats['service']} @ {ip}[/]\n"
                    f"  CPU: {stats['cpu']} Memory: {stats['memory']}"
                )
        
        if not alerts:
            return Panel("No active alerts", style="green")
        
        return Panel("\n".join(alerts[:5]), title="Active Alerts", style="red")

    def generate_dashboard(self):
        """Create complete dashboard layout"""
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body")
        )
        
        layout["header"].update(
            Panel(f"[bold]CPX Monitoring[/] | Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        )
        
        stats_table = self._create_stats_table()
        alert_panel = self._create_alerts_panel()
        
        layout["body"].split_row(
            Layout(stats_table, name="stats"),
            Layout(alert_panel, name="alerts")
        )
        
        return layout

    def start_live_view(self):
        """Run interactive dashboard"""
        try:
            with Live(self.generate_dashboard(), refresh_per_second=4, screen=True) as live:
                while True:
                    try:
                        if not self._refresh_data():
                            live.update(Panel("[red]Failed to update data[/]"))
                        else:
                            live.update(self.generate_dashboard())
                        time.sleep(5)
                    except KeyboardInterrupt:
                        logger.info("Dashboard stopped by user")
                        break
                    except Exception as e:
                        logger.error(f"Live update error: {e}")
                        time.sleep(5)
        except Exception as e:
            logger.critical(f"Dashboard failed: {e}")
            raise

class CPXMonitor:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.servers = []
        self.server_stats = {}
        self.last_update = None
        logger.info(f"Initializing CPXMonitor with base URL: {base_url}")
        # Initialize servers immediately when creating the monitor
        self.fetch_servers()

    def fetch_servers(self) -> List[str]:
        """Fetch all servers from CPX API"""
        try:
            logger.debug(f"Fetching servers from {self.base_url}/servers")
            response = requests.get(f"{self.base_url}/servers", timeout=5)
            response.raise_for_status()
            self.servers = response.json()
            logger.info(f"Successfully fetched {len(self.servers)} servers")
            return self.servers
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching servers: {e}")
            return []

    def fetch_server_stats(self, ip: str) -> Dict:
        """Fetch stats for a specific server"""
        try:
            logger.debug(f"Fetching stats for server {ip}")
            response = requests.get(f"{self.base_url}/{ip}", timeout=3)
            response.raise_for_status()
            stats = response.json()
            stats['ip'] = ip
            cpu = int(stats['cpu'][:-1])
            memory = int(stats['memory'][:-1])
            stats['status'] = 'Healthy' if cpu < 90 and memory < 90 else 'Unhealthy'
            logger.debug(f"Stats for {ip}: CPU {cpu}%, Memory {memory}%, Status {stats['status']}")
            return stats
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching stats for {ip}: {e}")
            return {}

    def update_all_stats(self):
        """Update stats for all servers"""
        logger.info("Updating stats for all servers")
        self.server_stats = {}
        for ip in self.servers:
            stats = self.fetch_server_stats(ip)
            if stats:
                self.server_stats[ip] = stats
        self.last_update = datetime.now()
        logger.info(f"Stats updated for {len(self.server_stats)}/{len(self.servers)} servers")

    def send_slack_alert(self, services):
        """Send alert to Slack via webhook - focused on unhealthy services"""
        SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
        if not SLACK_WEBHOOK_URL:
            logger.error("SLACK_WEBHOOK_URL not found in environment variables")
            return
        
        # Filter only unhealthy services
        unhealthy_services = [s for s in services if s[2] == "Unhealthy"]
        
        if not unhealthy_services:
            logger.info("No unhealthy services to alert")
            return

        logger.warning(f"Preparing Slack alert for {len(unhealthy_services)} unhealthy services")
        
        # Group by service name
        service_groups = defaultdict(list)
        for service in unhealthy_services:
            service_groups[service[0]].append(service)

        # Build the alert message
        alert_message = {
            "text": "Critical Services Alert",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Underprovisioned Unhealthy Services with less than 8 healthy instances",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Affected Services ({len(unhealthy_services)} instances):*"
                    }
                },
                {
                    "type": "divider"
                }
            ]
        }

        # Add each service group
        for service_name, instances in service_groups.items():
            alert_message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{service_name}* ({len(instances)} unhealthy instances)"
                }
            })
            
            for instance in instances:
                alert_message["blocks"].append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"• *IP:* `{instance[1]}`\n"
                            f"• *CPU:* `{instance[3]}`\n"
                            f"• *Memory:* `{instance[4]}`"
                        )
                    }
                })
            
            alert_message["blocks"].append({"type": "divider"})

        try:
            response = requests.post(
                SLACK_WEBHOOK_URL,
                json=alert_message,
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            response.raise_for_status()
            logger.info("Slack alert for underprovisioned services sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    def auto_remediate_services(self, services):
        """Pretend to scale services with high CPU/Memory and send simplified Slack notification"""
        SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
        if not SLACK_WEBHOOK_URL:
            logger.error("SLACK_WEBHOOK_URL not found in environment variables")
            return
            
        services_to_scale = set()
        
        for service in services:
            service_name = service[0]
            cpu = int(service[3].rstrip('%'))
            memory = int(service[4].rstrip('%'))
            
            # Check if CPU or memory is high
            if cpu > 80 or memory > 80:
                services_to_scale.add(service_name)
                logger.warning(f"Service {service_name} marked for scaling (CPU: {cpu}%, Memory: {memory}%)")

        if not services_to_scale:
            logger.info("No services require scaling")
            return

        logger.warning(f"Preparing to auto-scale {len(services_to_scale)} services: {', '.join(services_to_scale)}")

        # Build the simplified scaling notification message
        scaling_message = {
            "text": "Auto-scaling Actions Taken",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Auto-scaling Initiated",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "The following services were scaled based on CPU/Memory usage:"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "\n".join([f"• *{service}*" for service in services_to_scale])
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "Trigger: CPU or Memory > 80%"
                        }
                    ]
                }
            ]
        }

        try:
            response = requests.post(
                SLACK_WEBHOOK_URL,
                json=scaling_message,
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            response.raise_for_status()
            logger.info("Auto-scaling notification sent to Slack successfully")
        except Exception as e:
            logger.error(f"Failed to send scaling notification to Slack: {e}")

    def print_services_table(self):
        """Print all services in table format using tabulate"""
        if not self.servers:
            logger.error("No servers found - please check CPX server connection")
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
        logger.info("Displaying services table")
        print("\nCurrent Services Status:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def show_service_averages(self):
        """Print average CPU/Memory using tabulate"""
        if not self.servers:
            logger.error("No servers found - please check CPX server connection")
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
        logger.info("Displaying service averages")
        print("\nService Averages:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def flag_underprovisioned_services(self):
        """Flag services with fewer than 2 healthy instances using tabulate"""
        if not self.servers:
            logger.error("No servers found - please check CPX server connection")
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
            logger.warning(f"Found {len(table_data)} underprovisioned service instances")
            print("\n Underprovisioned Services (fewer than 2 healthy instances):")
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            self.send_slack_alert(table_data)
            # Auto-remediation for high CPU/Memory
            self.auto_remediate_services(table_data)
        else:
            logger.info("All services have sufficient healthy instances")
            print("\n All services have at least 2 healthy instances")

    def track_service(self, service_name: str):
        """Monitor a specific service over time with tabulate"""
        if not self.servers:
            logger.error("No servers found - please check CPX server connection")
            return
            
        logger.info(f"Starting to track service {service_name}")
        print(f"\n Monitoring {service_name} (press Ctrl+C to stop)...\n")
        
        def signal_handler(sig, frame):
            logger.info(f"Stopped tracking service {service_name}")
            print("\n Monitoring stopped")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)

        try:
            while True:
                self.update_all_stats()
                service_instances = [stats for stats in self.server_stats.values() 
                                   if stats['service'] == service_name]
                
                if not service_instances:
                    logger.error(f"No instances found for service: {service_name}")
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
                logger.debug(f"Current status for {service_name}: {len(service_instances)} instances")
                print(tabulate(table_data, headers=headers, tablefmt="grid"))
                print()  # Add space between updates
                
                time.sleep(5)
        except KeyboardInterrupt:
            logger.info(f"Stopped tracking service {service_name} by user request")
            print("\n Monitoring stopped")

def main():
    parser = argparse.ArgumentParser(description="CPX Monitoring Tool")
    parser.add_argument("--port", type=int, default=5008, help="Port of CPX server")
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

    # Command 5: Dashboard Service
    dashboard_parser = subparsers.add_parser("dashboard", help="Dashboard view")

    args = parser.parse_args()

    logger.info(f"Starting CPXMonitor with command: {args.command}")
    monitor = CPXMonitor(f"http://localhost:{args.port}")

    if args.command == "list":
        monitor.print_services_table()
    elif args.command == "averages":
        monitor.show_service_averages()
    elif args.command == "flag":
        monitor.flag_underprovisioned_services()
    elif args.command == "dashboard":
        # Clear terminal and start dashboard
        os.system('cls' if os.name == 'nt' else 'clear')
        TerminalDashboard(monitor).start_live_view()
    elif args.command == "track":
        if not args.service:
            logger.error("Service name not provided for track command")
            print("Error: --service argument is required for track command")
            sys.exit(1)
        monitor.track_service(args.service)

if __name__ == "__main__":
    main()