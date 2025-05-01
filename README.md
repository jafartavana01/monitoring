# M1 MacBook System Monitor

A real-time system monitoring dashboard for M1 MacBook, built with Python and Flask. This application provides a comprehensive view of your system's performance metrics with a modern, dark-themed interface.

## Features

- Real-time CPU usage monitoring
- Memory (RAM) usage tracking
- Disk usage statistics
- Network I/O monitoring with current bandwidth usage
- Battery status
- Top 10 CPU-intensive processes
- Network connections monitoring
- Temperature sensors (if available)

## Requirements

- Python 3.x
- Flask
- psutil
- Modern web browser

## Installation

1. Clone the repository:
```bash
git clone [your-repository-url]
cd m1-system-monitor
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Activate the virtual environment if not already activated:
```bash
source venv/bin/activate  # On macOS/Linux
```

2. Run the application:
```bash
python app.py
```

3. Open your web browser and navigate to:
```
http://127.0.0.1:3000
```

## Screenshots

[Add screenshots of your application here]

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request