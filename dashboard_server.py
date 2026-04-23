#!/usr/bin/env python3
"""
Dashboard Server for Hermes Agent Projects
Server untuk menampilkan semua proyek dengan akses dari Tailscale IP
"""

import http.server
import socketserver
import os
import socket
import sys
from datetime import datetime

PORT = 8080
HOST = '0.0.0.0'  # Listen on all interfaces

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler untuk dashboard"""
    
    def do_GET(self):
        # Serve file berdasarkan path
        if self.path == '/':
            self.path = '/index.html'
        elif self.path == '/dashboard':
            self.path = '/project_dashboard.html'
        
        # Serve file statis
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def log_message(self, format, *args):
        """Custom log format dengan timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {self.address_string()} - {format % args}")

def get_server_info():
    """Dapatkan informasi server"""
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return hostname, ip_address
    except:
        return "unknown", "unknown"

def main():
    """Main function untuk start server"""
    print("=" * 60)
    print("HERMES AGENT PROJECT DASHBOARD SERVER")
    print("=" * 60)
    
    # Ganti directory ke root
    os.chdir('/root')
    
    # Dapatkan info server
    hostname, local_ip = get_server_info()
    
    print(f"Server Hostname: {hostname}")
    print(f"Local IP: {local_ip}")
    print(f"Tailscale IP: 100.121.49.116")
    print(f"Dashboard URL: http://100.121.49.116:{PORT}")
    print(f"Dashboard URL: http://openclaw-hermes.tail92127.ts.net:{PORT}")
    print(f"Serving directory: {os.getcwd()}")
    print(f"Server started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("Available projects:")
    print("1. STNK Monitoring Dashboard - http://100.121.49.116:8085")
    print("2. Vehicle Monitoring System - http://100.121.49.116:8086")
    print("3. WhatsApp Bridge - http://100.121.49.116:3000")
    print("4. Main Dashboard (this) - http://100.121.49.116:8080")
    print("=" * 60)
    
    try:
        with socketserver.TCPServer((HOST, PORT), DashboardHandler) as httpd:
            print(f"Server running on port {PORT}...")
            print("Press Ctrl+C to stop")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()