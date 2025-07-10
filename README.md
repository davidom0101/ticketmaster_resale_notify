# Ticketmaster Resale Notifier

A Python script that monitors Ticketmaster for resale tickets and sends notifications when they become available.

## Features

- Monitors a Ticketmaster event page for resale tickets
- Sends desktop notifications via ntfy.sh when tickets are found
- Configurable check intervals and browser behavior
- Graceful shutdown handling
- Comprehensive logging

## Prerequisites

- Python 3.8+
- Playwright (for browser automation)
- ntfy.sh account (for notifications)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ticketmaster-resale-notify.git
   cd ticketmaster-resale-notify
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install Playwright browsers:
   ```bash
   playwright install
   ```

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your settings:
   ```ini
   # Required
   TICKETMASTER_URL="https://www.ticketmaster.ie/your-event"
   NTFY_TOPIC="your_ntfy_topic"
   
   # Optional (with defaults)
   # HEADLESS="False"
   # CHECK_INTERVAL_MIN="8.0,12.0"
   # BROWSER_TIMEOUT="360"
   # MAX_RETRIES="3"
   # RETRY_DELAY="5"
   # LOG_LEVEL="INFO"
   ```

## Usage

### Basic Usage

```bash
python cli.py
```

### Command Line Options

```
usage: cli.py [-h] [--event-url EVENT_URL] [--ntfy-topic NTFY_TOPIC] [--headless] [--check-interval CHECK_INTERVAL]
              [--browser-timeout BROWSER_TIMEOUT] [--max-retries MAX_RETRIES] [--retry-delay RETRY_DELAY]
              [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [-v]

Monitor Ticketmaster for resale tickets and get notified when available.

options:
  -h, --help            show this help message and exit
  --event-url EVENT_URL
                        URL of the Ticketmaster event page to monitor (default: from .env)
  --ntfy-topic NTFY_TOPIC
                        ntfy.sh topic for notifications (default: from .env)
  --headless            run browser in headless mode (no GUI) (default: False)
  --check-interval CHECK_INTERVAL
                        random interval range in minutes between checks (format: min,max) (default: 8.0,12.0)
  --browser-timeout BROWSER_TIMEOUT
                        time in seconds to keep browser open when tickets are found (default: 360)
  --max-retries MAX_RETRIES
                        maximum number of retries for failed operations (default: 3)
  --retry-delay RETRY_DELAY
                        initial delay between retries in seconds (default: 5)
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        set the logging level (default: INFO)
  -v, --version         show program's version number and exit
```

## Running in Headless Mode

To run the browser in headless mode (no GUI), use the `--headless` flag:

```bash
python cli.py --headless
```

## Logging

Logs are written to both the console and `ticketmaster_scraper.log` in the project directory.

Set the log level to `DEBUG` for more detailed logging:

```bash
python cli.py --log-level DEBUG
```

## Running as a Service (Linux)

To run the script as a systemd service:

1. Create a service file at `~/.config/systemd/user/ticketmonitor.service`:
   ```ini
   [Unit]
   Description=Ticketmaster Resale Monitor
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/path/to/ticketmaster-resale-notify
   ExecStart=/usr/bin/python3 /path/to/ticketmaster-resale-notify/cli.py --headless
   Restart=always
   RestartSec=60
   Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"

   [Install]
   WantedBy=default.target
   ```

2. Enable and start the service:
   ```bash
   systemctl --user enable --now ticketmonitor.service
   ```

## License

MIT
