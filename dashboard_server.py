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

PORT = 8080
HOST = '127.0.0.1'  # Wajib 127.0.0.1 karena Tailscale Serve handle external

SKILLS_DIR = os.path.expanduser("~/.hermes/skills")

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler untuk dashboard + API skills"""

    def do_GET(self):
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

        if self.path == '/':
            self.path = '/project_dashboard.html'

        return http.server.SimpleHTTPRequestHandler.do_GET(self)

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
