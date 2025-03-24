# CPX Monitoring Tool

## Overview
The **CPX Monitoring Tool** is a command-line utility designed to provide visibility into microservices deployments on Cloud Provider X (CPX). It helps **Site Reliability Engineers (SREs)** monitor service health, resource utilization, and identify potential issues in their infrastructure.

## Features

### Core Functionality
- **Service Listing**: View all running services with their current status and resource usage.
- **Service Averages**: Calculate and display average CPU/memory usage by service type.
- **Health Monitoring**: Identify services with insufficient healthy instances.
- **Real-time Tracking**: Continuously monitor specific services until manually stopped.

### Advanced Capabilities
- **Automatic Health Status Determination** (Healthy/Unhealthy)
- **Formatted Tabular Output** for readability
- **Graceful Handling of API Errors**
- **Configurable Monitoring Intervals**
- **Support for Both IPv4 and IPv6**

---

## Installation

### Prerequisites
- Python **3.6 or higher**
- `pip` package manager

### Steps
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/am2308/cpx-monitor.git
   cd cpx-monitor
   ```

2. **Create and Activate a Virtual Environment (Recommended)**:
   ```bash
   python3 -m venv cpx
   source cpx/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

### Starting the CPX Server
To start the CPX mock server, run:
```bash
python3 cpx_server.py <port> #5008
```

### Monitoring Tool Commands

#### **1. List All Services**
```bash
python3 monitor_cpx.py --port 5008 list
```

#### **2. Show Service Averages**
```bash
python3 monitor_cpx.py --port 5008 averages
```

#### **3. Flag Underprovisioned Services**
```bash
python3 monitor_cpx.py --port 5008 flag
```

#### **4. Monitor a Specific Service (Press Ctrl+C to Stop)**
```bash
python3 monitor_cpx.py --port 8000 track --service <serviceName> #AuthService
```

### Command Options
| Option    | Description                      | Default |
|-----------|----------------------------------|---------|
| `--port`  | Port number of CPX server       | `5008`  |
| `--help`  | Show help message               | `N/A`   |

---

## Configuration

The tool can be configured by modifying these aspects:
- **Health Thresholds**: Edit the `CPXMonitor` class to change CPU/memory thresholds (**default: 90%**).
- **Monitoring Interval**: Change the sleep duration in the `monitor_service` method (**default: 5 seconds**).
- **Output Formatting**: Adjust string formatting in the print methods.

---

## Development Setup

### Project Structure
```
cpx-monitor/
├── monitor_cpx.py      # Main application code
├── cpx_server.py       # Provided mock server
├── test_cpx_monitor.py # Unit tests
├── requirements.txt    # Dependencies
└── README.md           # Documentation
```

### Dependencies
- `requests` (HTTP client library)
- `tabulate` (tabular formatting)
To install development dependencies:
```bash
pip install -r requirements.txt
```

---

## Testing

### Running Tests
```bash
python3 -m unittest test_cpx_monitor.py
```

### Test Coverage
To generate a coverage report:
```bash
pip install coverage
coverage run -m unittest test_cpx_monitor.py
coverage report -m
```

---

## Mock Server

The provided `cpx_server.py` serves as:
- A **mock CPX API server** for development.
- A **test fixture** for integration testing.
- An **example implementation reference**.

---

## Architecture

### Components
- **CPXMonitor Class**: Core functionality for interacting with CPX API.
- **Command Interface**: Handles user input and output formatting.
- **Mock Server**: Simulates the CPX API for testing.

### Data Flow
1. **User Executes a Command**.
2. **Tool Makes API Calls** to CPX Server.
3. **Processes and Analyzes Data**.
4. **Presents Formatted Results** to the User.

---

### Trade-offs Made:
1. **Polling Interval**: Chose 5s for monitoring as a balance between:
   - API load (lower frequency)
   - Responsiveness (higher frequency)

2. **Health Thresholds**: Hardcoded 90% thresholds because:
   - Simple to understand
   - Easy to modify
   - Alternative: Config file would add complexity

3. **Tabulate Library**: Chosen over manual formatting because:
   - Consistent output
   - Handles edge cases (long service names)
   - Built-in table formats

---

## Future Improvements

### **Planned Features**
- 🚀 **Alerting System**: Email/Slack notifications for critical issues.
- 📈 **Historical Data**: Store and visualize trends over time.
- ⚙ **Configuration File**: YAML/JSON config for thresholds and endpoints.
- 🐳 **Docker Support**: Containerize for easy deployment.

### **Potential Enhancements**
- ✅ Support for **Multiple CPX Servers**
- 🔒 **Authentication for API Endpoints**
- 📄 Export Capabilities (CSV, JSON)
- 🌐 Web Dashboard Interface

