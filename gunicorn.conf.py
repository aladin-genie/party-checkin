import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# Worker processes
workers = 2
worker_class = "sync"
worker_connections = 1000

# Timeouts
timeout = 120
keepalive = 2

# Logging
errorlog = "-"
accesslog = "-"
loglevel = "info"
capture_output = True
enable_stdio_inheritance = True

# Process naming
proc_name = 'party-checkin'
