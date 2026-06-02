#!/usr/bin/env python3
import os
import pty
import sys
import time

def main():
    cmd = [
        "rsync",
        "-avz",
        "--exclude", ".venv",
        "--exclude", ".git",
        "--exclude", ".pytest_cache",
        "--exclude", "__pycache__",
        "--exclude", "*.pyc",
        "--exclude", ".claude",
        "-e", "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        "./",
        "raspberry@192.168.138.141:~/SeeFire/"
    ]
    
    print(f"[Deploy] Spawning: {' '.join(cmd)}")
    
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
