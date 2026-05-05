#!/usr/bin/env python3
"""
Dashboard Server for Hermes Agent Projects
Server untuk menampilkan semua proyek + Skills & Capabilities
Dengan endpoint /api/skills yang membaca folder skill langsung
"""

import http.server
import socketserver
import os
import socket
import sys
import json
import subprocess
import re
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import urlparse

PORT = 8080
HOST = '127.0.0.1'  # Wajib 127.0.0.1 karena Tailscale Serve handle external

SKILLS_DIR = os.path.expanduser("~/.hermes/skills")

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler untuk dashboard + API skills + proxy to other dashboards"""

    # Proxy routes: path prefix -> (host, port)
    PROXY_ROUTES = {
        '/stnk': ('127.0.0.1', 8087),
        '/wdc': ('127.0.0.1', 8088),
        '/contact': ('127.0.0.1', 8082),
    }

    def do_GET(self):
        # Handle API endpoints
        if self.path == '/api/skills':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = get_skills_data()
            self.wfile.write(json.dumps(data, indent=2).encode())
            return

        if self.path == '/api/deepseek':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = get_deepseek_data()
            self.wfile.write(json.dumps(data, indent=2).encode())
            return

        # Handle proxy routes
        for path_prefix, (host, port) in self.PROXY_ROUTES.items():
            if self.path.startswith(path_prefix):
                self.proxy_request(host, port)
                return

        # Default: serve static files
        if self.path == '/':
            self.path = '/project_dashboard.html'
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        """Handle POST requests for proxied API endpoints"""
        for path_prefix, (host, port) in self.PROXY_ROUTES.items():
            if self.path.startswith(path_prefix):
                self.proxy_request(host, port, method='POST')
                return
        self.send_error(404, 'Not Found')

    def proxy_request(self, host, port, method='GET'):
        """Forward request to backend dashboard server"""
        # Strip the path prefix when forwarding
        proxy_path = self.path
        for path_prefix in self.PROXY_ROUTES:
            if self.path.startswith(path_prefix):
                proxy_path = self.path[len(path_prefix):]
                if not proxy_path:
                    proxy_path = '/'
                break

        url = f'http://{host}:{port}{proxy_path}'
        try:
            # Forward headers (excluding hop-by-hop headers)
            headers = {}
            for key, value in self.headers.items():
                if key.lower() not in ('host', 'connection', 'keep-alive', 'transfer-encoding'):
                    headers[key] = value

            req = Request(url, method=method, headers=headers)
            if method in ('POST', 'PUT') and self.headers.get('Content-Length'):
                content_length = int(self.headers['Content-Length'])
                req.data = self.rfile.read(content_length)

            with urlopen(req, timeout=10) as response:
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in ('transfer-encoding', 'connection', 'keep-alive'):
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(response.read())
        except URLError as e:
            # Handle HTTP errors (like 401, 404, 500) properly
            if hasattr(e, 'code'):
                # It's an HTTPError - forward the actual status code
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                if hasattr(e, 'read'):
                    body = e.read()
                    if body:
                        self.wfile.write(body)
                    else:
                        self.wfile.write(f'{{"error": "{str(e)}"}}'.encode())
                else:
                    self.wfile.write(f'{{"error": "{str(e)}"}}'.encode())
            else:
                # True network error
                self.send_response(502)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(f'{{"error": "Proxy error: {str(e)}"}}'.encode())
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(f'{{"error": "{str(e)}"}}'.encode())

    def log_message(self, format, *args):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {self.address_string()} - {format % args}")


def get_skills_data():
    """Baca semua skill dari folder skills dan return JSON"""
    skills = {}
    total = 0
    
    if not os.path.isdir(SKILLS_DIR):
        return {"categories": {}, "total": 0, "last_updated": datetime.now().isoformat()}
    
    for cat_dir in sorted(os.listdir(SKILLS_DIR)):
        cat_path = os.path.join(SKILLS_DIR, cat_dir)
        if not os.path.isdir(cat_path):
            continue
        
        cat_skills = []
        for skill_dir in sorted(os.listdir(cat_path)):
            skill_path = os.path.join(cat_path, skill_dir)
            skill_md = os.path.join(skill_path, "SKILL.md")
            if os.path.isfile(skill_md):
                total += 1
                # Baca description dari SKILL.md
                desc = ""
                try:
                    with open(skill_md, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('description:'):
                                desc = line.split('description:', 1)[1].strip().strip('"').strip("'")
                                break
                            if not line or line.startswith('---'):
                                continue
                except:
                    desc = ""
                
                cat_skills.append({
                    "name": skill_dir,
                    "description": desc[:200] if desc else ""
                })
        
        if cat_skills:
            skills[cat_dir] = {
                "count": len(cat_skills),
                "skills": cat_skills
            }
    
    return {
        "categories": skills,
        "total": total,
        "last_updated": datetime.now().isoformat()
    }


def get_server_info():
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return hostname, ip_address
    except:
        return "unknown", "unknown"


def get_deepseek_data():
    """Ambil data pemakaian Deepseek dari file JSON yang diupdate cronjob"""
    result = {
        "status": "offline",
        "account_balance": "¥0.00",
        "current_month_cost": "¥0.00",
        "total_requests": 0,
        "total_tokens": 0,
        "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "error": None
    }
    
    # Baca data dari file scraper v4 (diupdate cron tiap 5 menit)
    data_file = os.path.expanduser("~/.hermes/scripts/deepseek_data.json")
    if os.path.exists(data_file):
        try:
            with open(data_file) as f:
                data = json.load(f)
                result["status"] = "online" if "Error" not in data.get("account_balance", "") else "error"
                result["account_balance"] = data.get("account_balance", "¥0.00")
                result["current_month_cost"] = data.get("current_month_cost", "¥0.00")
                result["total_requests"] = data.get("total_requests", 0)
                result["total_tokens"] = data.get("total_tokens", 0)
                result["last_updated"] = data.get("last_updated", result["last_updated"])
        except Exception as e:
            result["error"] = f"Read error: {str(e)[:100]}"
    else:
        result["error"] = "Data file not found"
    
    return result


def main():
    print("=" * 60)
    print("HERMES AGENT DASHBOARD PORTAL")
    print("Dengan Skills & Capabilities Auto-Refresh")
    print("=" * 60)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    hostname, local_ip = get_server_info()
    
    print(f"Server Hostname: {hostname}")
    print(f"Local IP: {local_ip}")
    print(f"Dashboard URL: http://100.122.46.110:{PORT}")
    print(f"Serving directory: {os.getcwd()}")
    print(f"Skills dir: {SKILLS_DIR}")
    print(f"Server started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # Listen only on localhost since Tailscale Serve handles external access
        class ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        with ReusableTCPServer(('127.0.0.1', PORT), DashboardHandler) as httpd:
            print(f"Server running on port {PORT}...")
            print("API: http://localhost:8080/api/skills")
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
