from flask import Flask, jsonify
import psutil
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)

def get_network_connections():
    """Get network connections sorted by bandwidth usage"""
    try:
        connections = []
        # Get all network connections
        for conn in psutil.net_connections(kind='inet'):
            try:
                if conn.status == 'ESTABLISHED':
                    process = psutil.Process(conn.pid) if conn.pid else None
                    connections.append({
                        'pid': conn.pid,
                        'name': process.name() if process else 'Unknown',
                        'laddr': f"{conn.laddr.ip}:{conn.laddr.port}",
                        'raddr': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A",
                        'status': conn.status
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return connections
    except Exception as e:
        logging.error(f"Error getting network connections: {e}")
        return []

def get_system_stats():
    """Get detailed system statistics with M1-specific monitoring"""
    try:
        # CPU Information (M1-specific)
        cpu_info = {
            'cpu': psutil.cpu_percent(interval=1),
            'cpu_per_core': psutil.cpu_percent(interval=1, percpu=True),
            'cpu_freq_current': psutil.cpu_freq().current if hasattr(psutil.cpu_freq(), 'current') else 0,
            'cpu_count': psutil.cpu_count(),
            'cpu_count_logical': psutil.cpu_count(logical=True)
        }

        # Memory Information (Unified Memory for M1)
        memory = psutil.virtual_memory()
        memory_info = {
            'memory_percent': memory.percent,
            'memory_total': round(memory.total / (1024.0 ** 3), 2),  # GB
            'memory_used': round(memory.used / (1024.0 ** 3), 2),    # GB
            'memory_free': round(memory.free / (1024.0 ** 3), 2),    # GB
            'memory_active': round(memory.active / (1024.0 ** 3), 2) if hasattr(memory, 'active') else 0,
            'memory_inactive': round(memory.inactive / (1024.0 ** 3), 2) if hasattr(memory, 'inactive') else 0
        }

        # Network I/O with current bandwidth
        net_io = psutil.net_io_counters()
        net_io_prev = getattr(get_system_stats, 'net_io_prev', net_io)
        net_time_prev = getattr(get_system_stats, 'net_time_prev', time.time())
        
        current_time = time.time()
        time_delta = current_time - net_time_prev
        
        if time_delta > 0:
            rx_speed = (net_io.bytes_recv - net_io_prev.bytes_recv) / time_delta
            tx_speed = (net_io.bytes_sent - net_io_prev.bytes_sent) / time_delta
        else:
            rx_speed = tx_speed = 0

        # Store current values for next calculation
        get_system_stats.net_io_prev = net_io
        get_system_stats.net_time_prev = current_time

        network_info = {
            'net_sent': round(net_io.bytes_sent / (1024.0 ** 2), 2),    # MB
            'net_recv': round(net_io.bytes_recv / (1024.0 ** 2), 2),    # MB
            'net_tx_speed': round(tx_speed / 1024, 2),  # KB/s
            'net_rx_speed': round(rx_speed / 1024, 2),  # KB/s
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
            'connections': get_network_connections()
        }

        # Disk Information (SSD)
        disk = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()
        disk_info = {
            'disk_percent': disk.percent,
            'disk_total': round(disk.total / (1024.0 ** 3), 2),      # GB
            'disk_used': round(disk.used / (1024.0 ** 3), 2),        # GB
            'disk_free': round(disk.free / (1024.0 ** 3), 2),        # GB
            'disk_read': round(disk_io.read_bytes / (1024.0 ** 3), 2) if disk_io else 0,
            'disk_write': round(disk_io.write_bytes / (1024.0 ** 3), 2) if disk_io else 0
        }

        # Sensors (Temperature, Fan, etc.)
        try:
            sensors = {
                'temperatures': psutil.sensors_temperatures(),
                'fans': psutil.sensors_fans() if hasattr(psutil, 'sensors_fans') else {}
            }
        except Exception:
            sensors = {'temperatures': {}, 'fans': {}}

        # Power/Battery Information
        try:
            battery = psutil.sensors_battery()
            power_info = {
                'battery_percent': round(battery.percent, 2) if battery else 0,
                'battery_plugged': battery.power_plugged if battery else None,
                'battery_left': battery.secsleft if battery and battery.secsleft != -1 else None
            }
        except Exception:
            power_info = {'battery_percent': 0, 'battery_plugged': None, 'battery_left': None}

        return {
            **cpu_info,
            **memory_info,
            **disk_info,
            **network_info,
            **power_info,
            'sensors': sensors
        }

    except Exception as e:
        logging.error(f"Error getting system stats: {e}")
        return None

def get_process_stats():
    """Get top 10 processes by CPU and memory usage"""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                # Skip processes with None values
                if pinfo['cpu_percent'] is not None and pinfo['memory_percent'] is not None:
                    processes.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'],
                        'cpu': pinfo['cpu_percent'],
                        'memory': pinfo['memory_percent']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError):
                continue
        
        # Only sort if we have valid processes
        if processes:
            return sorted(processes, key=lambda x: x['cpu'], reverse=True)[:10]
        return []
    except Exception as e:
        logging.error(f"Error in get_process_stats: {e}")
        return []

@app.route('/data')
def data():
    """Endpoint to fetch system statistics and process stats"""
    try:
        stats = get_system_stats()
        if stats is None:
            logging.error("Failed to get system stats")
            return jsonify({'error': 'Failed to fetch system statistics'}), 500
        
        processes = get_process_stats()
        logging.debug(f"System stats: {stats}")
        logging.debug(f"Process stats: {processes}")
        
        return jsonify({
            'system': stats,
            'processes': processes
        })
    except Exception as e:
        logging.error(f"Error in data endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    """Main page with system monitoring dashboard"""
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>System Monitor</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" rel="stylesheet">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #1e1e1e;
                color: #ffffff;
            }
            h1 {
                text-align: center;
                color: #00ff00;
                margin-bottom: 30px;
                font-size: 2.5em;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 20px;
                padding: 20px;
            }
            .card {
                background: #2d2d2d;
                border-radius: 15px;
                padding: 20px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
                transition: transform 0.3s ease;
            }
            .card:hover {
                transform: translateY(-5px);
            }
            .card-header {
                display: flex;
                align-items: center;
                margin-bottom: 15px;
            }
            .card i {
                font-size: 24px;
                color: #00ff00;
                margin-right: 10px;
            }
            .card h2 {
                margin: 0;
                color: #00ff00;
                font-size: 1.5em;
            }
            .value-display {
                font-size: 2em;
                text-align: center;
                margin: 15px 0;
                color: #00ff00;
            }
            canvas {
                width: 100% !important;
                height: 250px !important;
                margin-top: 10px;
            }
            .system-info {
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: #2d2d2d;
                border-radius: 15px;
                display: inline-block;
                margin-left: 50%;
                transform: translateX(-50%);
            }
            .system-info span {
                margin: 0 15px;
                color: #00ff00;
            }
            .process-list {
                background: #2d2d2d;
                border-radius: 8px;
                padding: 15px;
                margin-top: 20px;
            }
            .process-item {
                display: grid;
                grid-template-columns: 50px 1fr 100px 100px;
                padding: 8px;
                border-bottom: 1px solid #444;
            }
            .header {
                font-weight: bold;
                color: #00ff00;
            }
            .bar {
                background: #00ff00;
                height: 4px;
                border-radius: 2px;
                transition: width 0.3s ease;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
                margin-top: 15px;
            }
            .stat-item {
                text-align: center;
                padding: 10px;
                background: #222;
                border-radius: 8px;
            }
            .stat-item i {
                display: block;
                font-size: 24px;
                margin-bottom: 5px;
            }
            .stat-item span {
                display: block;
                font-size: 1.2em;
                margin: 5px 0;
            }
            .stat-item small {
                color: #888;
            }
            .temp-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 10px;
                margin-top: 15px;
            }
            .temp-item {
                background: #222;
                padding: 10px;
                border-radius: 8px;
                text-align: center;
            }
            .network-stats {
                margin: 20px 0;
            }
            .stat-row {
                display: flex;
                justify-content: center;
                gap: 30px;
            }
            .network-table {
                margin-top: 20px;
                overflow-x: auto;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                color: #fff;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #444;
            }
            th {
                background-color: #1e1e1e;
                color: #00ff00;
            }
            tr:hover {
                background-color: #383838;
            }
        </style>
    </head>
    <body>
        <h1><i class="fas fa-microchip"></i> System Monitor</h1>
        <div id="systemInfo" class="system-info">
            <span id="cpuCount"><i class="fas fa-microchip"></i> CPU Cores: --</span>
            <span id="cpuFreq"><i class="fas fa-tachometer-alt"></i> CPU Frequency: -- MHz</span>
            <span id="totalRam"><i class="fas fa-memory"></i> Total RAM: -- GB</span>
        </div>
        <div class="container">
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-microchip"></i>
                    <h2>CPU Usage</h2>
                </div>
                <div id="cpuValue" class="value-display">0%</div>
                <canvas id="cpuChart"></canvas>
            </div>
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-memory"></i>
                    <h2>Memory Usage</h2>
                </div>
                <div id="memoryValue" class="value-display">0%</div>
                <canvas id="memoryChart"></canvas>
            </div>
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-hdd"></i>
                    <h2>Disk Usage</h2>
                </div>
                <div id="diskValue" class="value-display">0%</div>
                <canvas id="diskChart"></canvas>
            </div>
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-network-wired"></i>
                    <h2>Network I/O</h2>
                </div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <i class="fas fa-upload"></i>
                        <span id="netSent">0 MB</span>
                        <small>Sent</small>
                    </div>
                    <div class="stat-item">
                        <i class="fas fa-download"></i>
                        <span id="netRecv">0 MB</span>
                        <small>Received</small>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-battery-full"></i>
                    <h2>Battery Status</h2>
                </div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <span id="batteryPercent">--%</span>
                        <small>Charge</small>
                    </div>
                    <div class="stat-item">
                        <span id="batteryStatus">--</span>
                        <small>Status</small>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-thermometer-half"></i>
                    <h2>Temperature</h2>
                </div>
                <div id="tempReadings" class="temp-grid">
                    <!-- Temperature readings will be inserted here -->
                </div>
            </div>
        </div>
        <div class="container">
            <div class="card" style="grid-column: 1 / -1;">
                <div class="card-header">
                    <i class="fas fa-network-wired"></i>
                    <h2>Network Connections</h2>
                </div>
                <div class="network-stats">
                    <div class="stat-row">
                        <div class="stat-item">
                            <i class="fas fa-upload"></i>
                            <span id="txSpeed">0 KB/s</span>
                            <small>Upload Speed</small>
                        </div>
                        <div class="stat-item">
                            <i class="fas fa-download"></i>
                            <span id="rxSpeed">0 KB/s</span>
                            <small>Download Speed</small>
                        </div>
                    </div>
                </div>
                <div class="network-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Process</th>
                                <th>PID</th>
                                <th>Local Address</th>
                                <th>Remote Address</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody id="networkConnections">
                            <!-- Network connections will be inserted here -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <div class="container">
            <h2>Top 10 Processes</h2>
            <div class="process-list">
                <div class="process-item header">
                    <div>PID</div>
                    <div>Name</div>
                    <div>CPU %</div>
                    <div>Memory %</div>
                </div>
                <div id="processList"></div>
            </div>
        </div>
        <script>
            const createChart = (ctx, label, color) => {
                return new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: Array(60).fill(''),
                        datasets: [{
                            label: label,
                            data: Array(60).fill(0),
                            borderColor: color,
                            backgroundColor: color + '33',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                grid: {
                                    color: '#333'
                                },
                                ticks: {
                                    color: '#fff'
                                }
                            },
                            x: {
                                grid: {
                                    color: '#333'
                                },
                                ticks: {
                                    color: '#fff'
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                labels: {
                                    color: '#fff'
                                }
                            }
                        }
                    }
                });
            };

            const charts = {
                cpu: createChart(document.getElementById('cpuChart').getContext('2d'), 
                               'CPU Usage (%)', '#00ff00'),
                memory: createChart(document.getElementById('memoryChart').getContext('2d'), 
                                  'Memory Usage (%)', '#00ffff'),
                disk: createChart(document.getElementById('diskChart').getContext('2d'), 
                                'Disk Usage (%)', '#ff00ff')
            };

            function formatBytes(bytes, decimals = 2) {
                if (bytes === 0) return '0 B';
                const k = 1024;
                const dm = decimals < 0 ? 0 : decimals;
                const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
            }

            function updateSystemInfo(data) {
                document.getElementById('cpuCount').innerHTML = 
                    `<i class="fas fa-microchip"></i> CPU Cores: ${data.cpu_count}`;
                document.getElementById('cpuFreq').innerHTML = 
                    `<i class="fas fa-tachometer-alt"></i> CPU Frequency: ${Math.round(data.cpu_freq_current)} MHz`;
                document.getElementById('totalRam').innerHTML = 
                    `<i class="fas fa-memory"></i> Total RAM: ${data.memory_total} GB`;
            }

            function updateValue(id, value) {
                document.getElementById(id).textContent = `${Math.round(value)}%`;
            }

            function updateProcessList(processes) {
                const container = document.getElementById('processList');
                container.innerHTML = '';
                
                processes.forEach(proc => {
                    const item = document.createElement('div');
                    item.className = 'process-item';
                    item.innerHTML = `
                        <div>${proc.pid}</div>
                        <div>${proc.name}</div>
                        <div>
                            ${proc.cpu.toFixed(1)}%
                            <div class="bar" style="width: ${proc.cpu}%"></div>
                        </div>
                        <div>
                            ${proc.memory.toFixed(1)}%
                            <div class="bar" style="width: ${proc.memory}%"></div>
                        </div>
                    `;
                    container.appendChild(item);
                });
            }

            function updateHardwareInfo(data) {
                // Update network stats
                document.getElementById('netSent').textContent = formatBytes(data.net_sent * 1024 * 1024);
                document.getElementById('netRecv').textContent = formatBytes(data.net_recv * 1024 * 1024);

                // Update battery info
                const batteryPercent = document.getElementById('batteryPercent');
                const batteryStatus = document.getElementById('batteryStatus');
                if (data.battery_percent > 0) {
                    batteryPercent.textContent = `${data.battery_percent}%`;
                    batteryStatus.textContent = data.battery_plugged ? 'Plugged In' : 'On Battery';
                } else {
                    batteryPercent.textContent = 'N/A';
                    batteryStatus.textContent = 'No Battery';
                }

                // Update temperature readings
                const tempReadings = document.getElementById('tempReadings');
                tempReadings.innerHTML = '';
                if (data.temperatures) {
                    Object.entries(data.temperatures).forEach(([sensor, readings]) => {
                        readings.forEach(([label, temp]) => {
                            const tempItem = document.createElement('div');
                            tempItem.className = 'temp-item';
                            tempItem.innerHTML = `
                                <small>${label || sensor}</small>
                                <div>${temp.toFixed(1)}°C</div>
                            `;
                            tempReadings.appendChild(tempItem);
                        });
                    });
                } else {
                    tempReadings.innerHTML = '<div class="temp-item">No temperature sensors available</div>';
                }
            }

            function updateNetworkInfo(data) {
                // Update network speeds
                document.getElementById('txSpeed').textContent = `${data.net_tx_speed.toFixed(2)} KB/s`;
                document.getElementById('rxSpeed').textContent = `${data.net_rx_speed.toFixed(2)} KB/s`;

                // Update network connections table
                const tbody = document.getElementById('networkConnections');
                tbody.innerHTML = '';
                
                data.connections.forEach(conn => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${conn.name}</td>
                        <td>${conn.pid}</td>
                        <td>${conn.laddr}</td>
                        <td>${conn.raddr}</td>
                        <td>${conn.status}</td>
                    `;
                    tbody.appendChild(row);
                });
            }

            function updateCharts() {
                fetch('/data')
                    .then(response => {
                        if (!response.ok) throw new Error('Network response was not ok');
                        return response.json();
                    })
                    .then(data => {
                        // Existing updates...
                        updateValue('cpuValue', data.system.cpu);
                        updateValue('memoryValue', data.system.memory_percent);
                        updateValue('diskValue', data.system.disk_percent);
                        updateSystemInfo(data.system);
                        updateHardwareInfo(data.system);
                        updateNetworkInfo(data.system);

                        // Update charts
                        const updateChart = (chart, value) => {
                            chart.data.datasets[0].data.push(value);
                            chart.data.datasets[0].data.shift();
                            chart.update('none');
                        };

                        updateChart(charts.cpu, data.system.cpu);
                        updateChart(charts.memory, data.system.memory_percent);
                        updateChart(charts.disk, data.system.disk_percent);

                        // Update process list
                        updateProcessList(data.processes);
                    })
                    .catch(error => console.error('Error fetching data:', error));
            }

            // Update every second
            setInterval(updateCharts, 1000);
            // Initial update
            updateCharts();
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)