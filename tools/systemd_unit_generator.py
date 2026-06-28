#!/usr/bin/env python3
"""
Systemd Unit Generator
Interactive wizard and command-line utility to generate compliant Linux systemd service, timer,
or path unit configuration files with validation checks.
"""

import sys
import os
import argparse

def validate_executable_path(path):
    if not path:
        return False
    # Executable path in systemd must be absolute or start with a dynamic specifier
    parts = path.strip().split()
    if not parts:
        return False
    exec_part = parts[0]
    if exec_part.startswith('/') or exec_part.startswith('%') or exec_part.startswith('@') or exec_part.startswith('-'):
        return True
    return False

def generate_service(args):
    lines = []
    lines.append("[Unit]")
    lines.append(f"Description={args.description or 'Custom Background Service'}")
    if args.after:
        lines.append(f"After={args.after}")
    if args.requires:
        lines.append(f"Requires={args.requires}")
    lines.append("")
    lines.append("[Service]")
    lines.append(f"Type={args.type or 'simple'}")
    
    if args.user:
        lines.append(f"User={args.user}")
    if args.group:
        lines.append(f"Group={args.group}")
        
    if args.workdir:
        lines.append(f"WorkingDirectory={args.workdir}")
        
    # ExecStart is required
    exec_start = args.exec_start
    if not exec_start:
        if not sys.stdin.isatty():
            print("Error: --exec-start is required for service units in non-interactive mode.", file=sys.stderr)
            sys.exit(1)
        exec_start = input("Enter ExecStart command (e.g., /usr/bin/python3 /app/main.py): ").strip()
        
    if not validate_executable_path(exec_start):
        print(f"Warning: ExecStart path '{exec_start}' might not be absolute. Systemd usually requires absolute paths.", file=sys.stderr)
        
    lines.append(f"ExecStart={exec_start}")
    
    if args.exec_stop:
        lines.append(f"ExecStop={args.exec_stop}")
        
    if args.restart:
        lines.append(f"Restart={args.restart}")
        lines.append(f"RestartSec={args.restart_sec or '5s'}")
        
    if args.env:
        for env_var in args.env:
            lines.append(f"Environment={env_var}")
            
    if args.env_file:
        lines.append(f"EnvironmentFile={args.env_file}")
        
    lines.append("")
    lines.append("[Install]")
    lines.append(f"WantedBy={args.wanted_by or 'multi-user.target'}")
    
    return "\n".join(lines) + "\n"

def generate_timer(args):
    lines = []
    lines.append("[Unit]")
    lines.append(f"Description={args.description or 'Custom Background Timer'}")
    lines.append("")
    lines.append("[Timer]")
    
    on_calendar = args.on_calendar
    on_boot_sec = args.on_boot_sec
    on_unit_active_sec = args.on_unit_active_sec
    
    if not (on_calendar or on_boot_sec or on_unit_active_sec):
        if not sys.stdin.isatty():
            print("Error: At least one timer trigger (--on-calendar, --on-boot-sec, --on-unit-active-sec) is required.", file=sys.stderr)
            sys.exit(1)
        print("Select trigger type:")
        print("1. Calendar schedule (e.g., daily, hourly, mon-fri 10:00)")
        print("2. Relative to boot (e.g., 10min after boot)")
        choice = input("Choice (1-2): ").strip()
        if choice == "1":
            on_calendar = input("Enter OnCalendar schedule (default: daily): ").strip() or "daily"
        else:
            on_boot_sec = input("Enter OnBootSec delay (default: 15min): ").strip() or "15min"
            
    if on_calendar:
        lines.append(f"OnCalendar={on_calendar}")
    if on_boot_sec:
        lines.append(f"OnBootSec={on_boot_sec}")
    if on_unit_active_sec:
        lines.append(f"OnUnitActiveSec={on_unit_active_sec}")
        
    if args.timer_unit:
        lines.append(f"Unit={args.timer_unit}")
        
    lines.append("")
    lines.append("[Install]")
    lines.append("WantedBy=timers.target")
    
    return "\n".join(lines) + "\n"

def generate_path(args):
    lines = []
    lines.append("[Unit]")
    lines.append(f"Description={args.description or 'Custom File Path Monitor'}")
    lines.append("")
    lines.append("[Path]")
    
    path_modified = args.path_modified
    path_exists = args.path_exists
    
    if not (path_modified or path_exists):
        if not sys.stdin.isatty():
            print("Error: Either --path-modified or --path-exists is required for path units.", file=sys.stderr)
            sys.exit(1)
        path_modified = input("Enter path to monitor for modifications (absolute path): ").strip()
        
    if path_modified:
        lines.append(f"PathModified={path_modified}")
    if path_exists:
        lines.append(f"PathExists={path_exists}")
        
    if args.path_unit:
        lines.append(f"Unit={args.path_unit}")
        
    lines.append("")
    lines.append("[Install]")
    lines.append("WantedBy=multi-user.target")
    
    return "\n".join(lines) + "\n"

def interactive_wizard():
    print("Welcome to the Systemd Unit Generator Wizard!")
    print("==============================================")
    print("Select the type of systemd unit to generate:")
    print("1. Service (.service) - Runs a daemon, process, or script")
    print("2. Timer (.timer) - Runs a service on a periodic schedule or boot trigger")
    print("3. Path (.path) - Triggers a service when files or directories change")
    
    try:
        choice = input("Enter selection (1-3): ").strip()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)
        
    parser = argparse.ArgumentParser()
    args, unknown = parser.parse_known_args()
    
    # Common settings
    args.description = input("Enter description: ").strip()
    
    if choice == "1":
        args.exec_start = input("Enter ExecStart command (absolute path recommended): ").strip()
        args.type = input("Service Type (simple/forking/oneshot/notify) [simple]: ").strip() or "simple"
        args.user = input("User to run as (optional): ").strip() or None
        args.group = input("Group to run as (optional): ").strip() or None
        args.workdir = input("Working directory (optional): ").strip() or None
        args.after = input("Run after service (optional, e.g. network.target): ").strip() or "network.target"
        args.requires = input("Requires service (optional): ").strip() or None
        restart_choice = input("Auto-restart on failure? (y/n) [y]: ").strip().lower() or 'y'
        if restart_choice in ('y', 'yes'):
            args.restart = "on-failure"
            args.restart_sec = input("Restart delay [5s]: ").strip() or "5s"
        else:
            args.restart = None
            args.restart_sec = None
        args.env = []
        while True:
            env_input = input("Enter Environment variable KEY=VALUE (or press enter to skip): ").strip()
            if not env_input:
                break
            args.env.append(env_input)
        args.env_file = input("EnvironmentFile path (optional): ").strip() or None
        args.wanted_by = input("WantedBy target [multi-user.target]: ").strip() or "multi-user.target"
        
        return generate_service(args), "service"
        
    elif choice == "2":
        args.on_calendar = None
        args.on_boot_sec = None
        args.on_unit_active_sec = None
        
        print("\nConfigure timer triggers (press enter to skip options):")
        args.on_calendar = input("OnCalendar schedule (e.g. daily, hourly, weekly, *:00/15): ").strip() or None
        args.on_boot_sec = input("OnBootSec delay (e.g. 15min, 10s): ").strip() or None
        args.on_unit_active_sec = input("OnUnitActiveSec delay (e.g. 1h): ").strip() or None
        args.timer_unit = input("Unit to trigger (optional, defaults to same-named .service): ").strip() or None
        
        return generate_timer(args), "timer"
        
    elif choice == "3":
        args.path_modified = None
        args.path_exists = None
        
        print("\nConfigure path monitors (press enter to skip options):")
        args.path_modified = input("PathModified directory/file to watch: ").strip() or None
        args.path_exists = input("PathExists directory/file to check: ").strip() or None
        args.path_unit = input("Unit to trigger (optional, defaults to same-named .service): ").strip() or None
        
        return generate_path(args), "path"
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Generate systemd unit files (.service, .timer, .path).")
    subparsers = parser.add_subparsers(dest="unit_type", help="Type of unit to generate")
    
    # Service parser
    service_p = subparsers.add_parser("service", help="Generate a .service unit")
    service_p.add_argument("--description", help="Service description")
    service_p.add_argument("--exec-start", required=False, help="Executable command (ExecStart)")
    service_p.add_argument("--exec-stop", help="Shutdown command (ExecStop)")
    service_p.add_argument("--type", default="simple", choices=["simple", "forking", "oneshot", "dbus", "notify", "idle"], help="Service type")
    service_p.add_argument("--user", help="User execution context")
    service_p.add_argument("--group", help="Group execution context")
    service_p.add_argument("--workdir", help="WorkingDirectory path")
    service_p.add_argument("--after", default="network.target", help="After= target list")
    service_p.add_argument("--requires", help="Requires= unit list")
    service_p.add_argument("--restart", choices=["no", "on-success", "on-failure", "on-abnormal", "on-watchdog", "on-abort", "always"], help="Restart condition")
    service_p.add_argument("--restart-sec", default="5s", help="RestartSec time interval")
    service_p.add_argument("--env", nargs="+", help="Environment variables (KEY=VALUE)")
    service_p.add_argument("--env-file", help="EnvironmentFile path")
    service_p.add_argument("--wanted-by", default="multi-user.target", help="WantedBy target")
    
    # Timer parser
    timer_p = subparsers.add_parser("timer", help="Generate a .timer unit")
    timer_p.add_argument("--description", help="Timer description")
    timer_p.add_argument("--on-calendar", help="OnCalendar schedule expression")
    timer_p.add_argument("--on-boot-sec", help="OnBootSec trigger delay")
    timer_p.add_argument("--on-unit-active-sec", help="OnUnitActiveSec trigger interval")
    timer_p.add_argument("--timer-unit", help="Unit to trigger (Unit)")
    
    # Path parser
    path_p = subparsers.add_parser("path", help="Generate a .path unit")
    path_p.add_argument("--description", help="Path monitor description")
    path_p.add_argument("--path-modified", help="PathModified watch target")
    path_p.add_argument("--path-exists", help="PathExists watch target")
    path_p.add_argument("--path-unit", help="Unit to trigger (Unit)")
    
    parser.add_argument("-o", "--output", help="Save unit configuration to specified file")
    
    # If no command arguments are provided, launch the interactive wizard
    if len(sys.argv) == 1:
        content, name = interactive_wizard()
        if content:
            if not sys.stdout.isatty():
                sys.stdout.write(content)
            else:
                print(f"\n--- Generated {name.capitalize()} Unit ---")
                print(content)
                save_choice = input("Do you want to save this to a file? (y/n) [n]: ").strip().lower()
                if save_choice in ('y', 'yes'):
                    filepath = input(f"Enter filename (default: custom.{name}): ").strip() or f"custom.{name}"
                    try:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"Saved unit successfully to '{filepath}'")
                    except Exception as e:
                        print(f"Error saving file: {e}")
        return
        
    args = parser.parse_args()
    
    if args.unit_type == "service":
        content = generate_service(args)
    elif args.unit_type == "timer":
        content = generate_timer(args)
    elif args.unit_type == "path":
        content = generate_path(args)
    else:
        parser.print_help()
        sys.exit(1)
        
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Unit configuration successfully saved to: {args.output}")
        except Exception as e:
            print(f"Error writing to file '{args.output}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        sys.stdout.write(content)

if __name__ == "__main__":
    main()
