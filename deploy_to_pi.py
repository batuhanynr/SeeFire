#!/usr/bin/env python3
import argparse
import os
import pty
import sys

def main():
    parser = argparse.ArgumentParser(description="Deploy SeeFire repo to Raspberry Pi")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete remote files that no longer exist locally, while preserving excluded runtime/model data.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what rsync would change without copying/deleting files.",
    )
    args = parser.parse_args()

    cmd = [
        "rsync",
        "-avz",
        "--itemize-changes",
        "--exclude", ".venv",
        "--exclude", ".git",
        "--exclude", ".pytest_cache",
        "--exclude", "__pycache__",
        "--exclude", "*.pyc",
        "--exclude", ".claude",
        "--exclude", ".env",
        "--exclude", "datasets/",
        "--exclude", "runs/",
        "--exclude", "runtime_data/",
        "--exclude", "m4_vision/models/",
        "--exclude", "*.pt",
        "--exclude", "*.zip",
        "-e", "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        "./",
        "raspberry@192.168.138.141:~/SeeFire/"
    ]

    if args.clean:
        cmd.insert(2, "--delete")
    if args.dry_run:
        cmd.insert(2, "--dry-run")
    
    print(f"[Deploy] Spawning: {' '.join(cmd)}")
    if args.clean:
        print("[Deploy] Clean mode: remote stale files will be deleted except excluded runtime/model data.")
    if args.dry_run:
        print("[Deploy] Dry run: no remote files will be changed.")
    
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(cmd[0], cmd)
    else:
        password_sent = False
        buffer = b""
        
        while True:
            try:
                data = os.read(fd, 1024)
                if not data:
                    break
                buffer += data
                sys.stdout.buffer.write(data)
                sys.stdout.flush()
                
                if b"password:" in buffer.lower() and not password_sent:
                    print("\n[Deploy] Sending password...")
                    os.write(fd, b"1111\n")
                    password_sent = True
                    buffer = b""
            except OSError:
                break
                
        _, status = os.waitpid(pid, 0)
        exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
        print(f"\n[Deploy] Complete. Exit code: {exit_code}")
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
