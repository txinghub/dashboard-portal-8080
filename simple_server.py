#!/usr/bin/env python3
import http.server
import socketserver
import os

PORT = 8080

# Change to root directory
os.chdir('/root')

# Custom handler to serve index.html by default
class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        elif self.path == '/dashboard':
            self.path = '/dashboard_simple.html'
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

# Start server
with socketserver.TCPServer(("127.0.0.1", PORT), MyHandler) as httpd:
    print(f"Server running at http://0.0.0.0:{PORT}")
    print(f"Dashboard: http://100.121.49.116:{PORT}")
    print(f"Press Ctrl+C to stop")
    httpd.serve_forever()