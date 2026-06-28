#!/usr/bin/env python3
"""
ssh_tunnel_manager.py - SSH Port Forwarding and Tunnel Manager
A tool to define, start, stop, monitor, and health-check SSH tunnels (local, remote, and dynamic SOCKS5 proxies)
using a simple JSON configuration. Runs tunnels in the background and validates connection status.
"""

import os
import sys
import json
import socket
import subprocess
import argparse
import time
import signal

# Default paths
DEFAULT_CONFIG_FILE = "ssh_tunnels.json"
STATE_FILE = os.path.expanduser("~/.ssh_tunnels_state.json")

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

def is_port_open(host, port):
    """Checks if a local or remote port is open/listening."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect((host, int(port)))
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def get_state():
    """Loads the active state of background tunnels."""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    """Saves the active state of background tunnels."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving state: {e}", file=sys.stderr)

def is_process_running(pid):
    """Checks if a process ID is currently running."""
    if pid <= 0:
        return False
    
    if sys.platform == 'win32':
        # Windows process check
        try:
            # tasklist check for PID
            output = subprocess.check_output(
                f'tasklist /FI "PID eq {pid}" /NH', 
                shell=True, 
                text=True
            )
            return str(pid) in output
        except Exception:
            return False
    else:
        # Unix process check (send signal 0)
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

def terminate_process(pid):
    """Terminates a process by ID."""
    if not is_process_running(pid):
        return True
    try:
        if sys.platform == 'win32':
            subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            if is_process_running(pid):
                os.kill(pid, signal.SIGKILL)
        return True
    except Exception:
        return False

def create_template_config(path):
    """Generates a template JSON configuration file."""
    template = [
        {
            "name": "local-db-tunnel",
            "type": "local",
            "ssh_host": "bastion.example.com",
            "ssh_user": "username",
            "ssh_port": 22,
            "identity_file": "~/.ssh/id_rsa",
            "local_host": "127.0.0.1",
            "local_port": 5432,
            "remote_host": "rds-postgres.internal.net",
            "remote_port": 5432,
            "description": "Forward local PostgreSQL port 5432 to AWS RDS database"
        },
        {
            "name": "socks5-proxy",
            "type": "dynamic",
            "ssh_host": "vps.my-server.com",
            "ssh_user": "ubuntu",
            "ssh_port": 22,
            "local_port": 1080,
            "description": "SOCKS5 Dynamic proxy for web traffic"
        },
        {
            "name": "remote-web-tunnel",
            "type": "remote",
            "ssh_host": "public-server.com",
            "ssh_user": "root",
            "local_host": "127.0.0.1",
            "local_port": 8000,
            "remote_port": 80,
            "description": "Expose local development web server on public port 80"
        }
    ]
    try:
        with open(path, 'w') as f:
            json.dump(template, f, indent=4)
        print(f"{GREEN}Created configuration template in: {path}{RESET}")
        return True
    except Exception as e:
        print(f"{RED}Error creating template config: {e}{RESET}", file=sys.stderr)
        return False

def load_config(path):
    if not os.path.exists(path):
        print(f"{YELLOW}Warning: Configuration file '{path}' not found.{RESET}")
        return []
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"{RED}Error loading configuration: {e}{RESET}", file=sys.stderr)
        return []

def build_ssh_command(t):
    """Constructs the SSH command arguments for the tunnel configuration."""
    cmd = ["ssh", "-N", "-o", "ExitOnForwardFailure=yes"]
    
    # Port configuration
    port = t.get("ssh_port", 22)
    cmd.extend(["-p", str(port)])
    
    # Key identity file
    if t.get("identity_file"):
        identity_path = os.path.expanduser(t["identity_file"])
        cmd.extend(["-i", identity_path])
        
    # Server Alive Keepalives
    cmd.extend(["-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3"])
    
    # Strict Host Key Checking options can be customized or bypassed for dev
    cmd.extend(["-o", "StrictHostKeyChecking=accept-new"])

    # Forwarding types
    t_type = t.get("type", "local").lower()
    
    local_host = t.get("local_host", "127.0.0.1")
    local_port = t.get("local_port")
    remote_host = t.get("remote_host", "127.0.0.1")
    remote_port = t.get("remote_port")

    if t_type == "local":
        if not local_port or not remote_port:
            raise ValueError("Local tunnel requires 'local_port' and 'remote_port'")
        cmd.extend(["-L", f"{local_host}:{local_port}:{remote_host}:{remote_port}"])
        
    elif t_type == "remote":
        if not remote_port or not local_port:
            raise ValueError("Remote tunnel requires 'remote_port' and 'local_port'")
        # Remote forwarding binds on remote host's loopback or wildcard
        cmd.extend(["-R", f"{remote_port}:{local_host}:{local_port}"])
        
    elif t_type == "dynamic":
        if not local_port:
            raise ValueError("Dynamic SOCKS5 tunnel requires 'local_port'")
        cmd.extend(["-D", f"{local_host}:{local_port}"])
    else:
        raise ValueError(f"Unknown tunnel type: {t_type}")

    # Destination host
    user = t.get("ssh_user")
    host = t.get("ssh_host")
    if not host:
        raise ValueError("Tunnel configuration requires 'ssh_host'")
        
    destination = f"{user}@{host}" if user else host
    cmd.append(destination)
    
    return cmd

def start_tunnel(t):
    """Spawns the SSH tunnel command in the background."""
    name = t["name"]
    state = get_state()
    
    # Check if already running in state
    if name in state:
        pid = state[name]["pid"]
        if is_process_running(pid):
            print(f"Tunnel '{name}' is already running with PID {pid}.")
            return True
            
    try:
        cmd = build_ssh_command(t)
    except ValueError as e:
        print(f"{RED}Invalid config for '{name}': {e}{RESET}")
        return False

    print(f"Starting tunnel '{name}'...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        # Start background subprocess
        # stdout/stderr are redirected to avoid blocking or spamming the terminal
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            close_fds=(sys.platform != 'win32')
        )
        
        # Give it a second to establish connection and check for immediate exit errors
        time.sleep(1.0)
        p.poll()
        
        if p.returncode is not None:
            # Process terminated immediately, retrieve error
            _, stderr_data = p.communicate()
            err_msg = stderr_data.decode('utf-8', errors='replace').strip()
            print(f"{RED}Failed to start tunnel '{name}': {err_msg}{RESET}")
            return False
            
        # Update running state
        state[name] = {
            "pid": p.pid,
            "type": t.get("type"),
            "local_host": t.get("local_host", "127.0.0.1"),
            "local_port": t.get("local_port"),
            "remote_port": t.get("remote_port"),
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_state(state)
        
        # Check port status
        local_host = t.get("local_host", "127.0.0.1")
        local_port = t.get("local_port")
        t_type = t.get("type", "local").lower()
        
        if t_type in ["local", "dynamic"]:
            if is_port_open(local_host, local_port):
                print(f"{GREEN}Success! Tunnel '{name}' running. Listening locally on {local_host}:{local_port}. PID: {p.pid}{RESET}")
            else:
                print(f"{YELLOW}Warning: SSH process started (PID {p.pid}), but local port {local_port} does not appear open yet.{RESET}")
        else:
            print(f"{GREEN}Success! Remote tunnel '{name}' started (PID {p.pid}). Exposing local port to remote port {t.get('remote_port')}{RESET}")
            
        return True
    except Exception as e:
        print(f"{RED}Error starting tunnel '{name}': {e}{RESET}")
        return False

def stop_tunnel(name):
    """Stops a background tunnel by name."""
    state = get_state()
    if name not in state:
        print(f"Tunnel '{name}' is not running (no state found).")
        return False
        
    pid = state[name]["pid"]
    print(f"Stopping tunnel '{name}' (PID: {pid})...")
    
    success = terminate_process(pid)
    
    # Remove from state anyway
    del state[name]
    save_state(state)
    
    if success:
        print(f"{GREEN}Stopped tunnel '{name}'.{RESET}")
    else:
        print(f"{YELLOW}Process {pid} for tunnel '{name}' could not be terminated (it may have already exited).{RESET}")
    return True

def stop_all_tunnels():
    state = get_state()
    if not state:
        print("No active tunnels to stop.")
        return
        
    names = list(state.keys())
    for name in names:
        stop_tunnel(name)

def check_status(config_tunnels):
    """Prints a formatted status table of all defined tunnels and active state."""
    state = get_state()
    
    print(f"\n{BOLD}{CYAN}=== SSH Tunnel Status ==={RESET}")
    print(f"{'Tunnel Name':<20} | {'Type':<8} | {'Port':<8} | {'PID':<8} | {'Process':<8} | {'Connection':<10}")
    print("-" * 75)
    
    # Get all names from config and state combined
    all_names = set(state.keys()) | {t["name"] for t in config_tunnels}
    
    for name in sorted(all_names):
        # Find config and state details
        cfg = next((t for t in config_tunnels if t["name"] == name), None)
        st = state.get(name)
        
        t_type = cfg.get("type", "local") if cfg else (st.get("type") if st else "unknown")
        
        # Determine ports
        port_info = "N/A"
        if cfg:
            if t_type in ["local", "dynamic"]:
                port_info = f"L:{cfg.get('local_port')}"
            else:
                port_info = f"R:{cfg.get('remote_port')}"
        elif st:
            if t_type in ["local", "dynamic"]:
                port_info = f"L:{st.get('local_port')}"
            else:
                port_info = f"R:{st.get('remote_port')}"
                
        pid = st.get("pid") if st else None
        
        # Evaluate states
        proc_status = "STOPPED"
        conn_status = "N/A"
        
        if pid:
            if is_process_running(pid):
                proc_status = f"{GREEN}RUNNING{RESET}"
                
                # Check connection port health
                l_host = st.get("local_host", "127.0.0.1")
                l_port = st.get("local_port")
                
                if t_type in ["local", "dynamic"]:
                    if is_port_open(l_host, l_port):
                        conn_status = f"{GREEN}ACTIVE{RESET}"
                    else:
                        conn_status = f"{RED}PORT CLOSED{RESET}"
                else:
                    # Remote tunnels cannot easily check if the remote side is open locally, so just say OK
                    conn_status = f"{GREEN}OK (Remote){RESET}"
            else:
                proc_status = f"{RED}DEAD{RESET}"
                conn_status = f"{RED}DISCONNECTED{RESET}"
                # Clean up dead item from state
                del state[name]
                save_state(state)
        else:
            proc_status = f"{DIM}INACTIVE{RESET}"
            conn_status = f"{DIM}N/A{RESET}"
            
        pid_str = str(pid) if pid else "-"
        print(f"{name:<20} | {t_type:<8} | {port_info:<8} | {pid_str:<8} | {proc_status:<8} | {conn_status:<10}")
    print()

def main():
    parser = argparse.ArgumentParser(
        description="SSH Tunnel and Port Forwarding CLI Manager."
    )
    parser.add_argument(
        '-c', '--config', 
        default=DEFAULT_CONFIG_FILE,
        help=f"Path to JSON configuration file (default: {DEFAULT_CONFIG_FILE})"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Management commands")
    
    # Init template config
    subparsers.add_parser("init", help="Create a template JSON config file")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start SSH tunnels")
    start_parser.add_argument("name", nargs="?", help="Name of the tunnel to start. If omitted, starts all configured tunnels.")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop SSH tunnels")
    stop_parser.add_argument("name", nargs="?", help="Name of the tunnel to stop. If omitted, stops all running tunnels.")
    
    # Status command
    subparsers.add_parser("status", help="Show active status and connection health of all tunnels")
    
    # List command
    subparsers.add_parser("list", help="List defined tunnel configurations")
    
    args = parser.parse_args()
    
    if args.command == "init":
        create_template_config(args.config)
        sys.exit(0)
        
    # Load configuration
    tunnels = load_config(args.config)
    
    if args.command == "start":
        if not tunnels:
            print(f"{RED}No tunnels configured. Please run '{sys.argv[0]} init' to create a config template.{RESET}")
            sys.exit(1)
            
        if args.name:
            # Start specific tunnel
            target = next((t for t in tunnels if t["name"] == args.name), None)
            if not target:
                print(f"{RED}Error: Tunnel '{args.name}' not found in configuration.{RESET}")
                sys.exit(1)
            start_tunnel(target)
        else:
            # Start all tunnels
            for t in tunnels:
                start_tunnel(t)
                
    elif args.command == "stop":
        if args.name:
            stop_tunnel(args.name)
        else:
            stop_all_tunnels()
            
    elif args.command == "status":
        check_status(tunnels)
        
    elif args.command == "list":
        if not tunnels:
            print("No tunnels configured.")
            sys.exit(0)
        print(f"\n{BOLD}{CYAN}=== Configured Tunnels ==={RESET}")
        for t in tunnels:
            print(f"Name: {BOLD}{t['name']}{RESET} ({t.get('type', 'local')})")
            print(f"  SSH Server:  {t.get('ssh_user')}@{t.get('ssh_host')}:{t.get('ssh_port', 22)}")
            if t.get('type') == 'local':
                print(f"  Forward:     Local port {t.get('local_port')} -> {t.get('remote_host')}:{t.get('remote_port')}")
            elif t.get('type') == 'remote':
                print(f"  Forward:     Remote port {t.get('remote_port')} -> {t.get('local_host', '127.0.0.1')}:{t.get('local_port')}")
            elif t.get('type') == 'dynamic':
                print(f"  Proxy:       SOCKS5 local proxy on port {t.get('local_port')}")
            if t.get('description'):
                print(f"  Description: {t.get('description')}")
            print()
            
    else:
        # Default behavior: show status
        check_status(tunnels)

if __name__ == "__main__":
    main()
