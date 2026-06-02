#!/usr/bin/env python3
import os
import pty
import sys
import time

def run_command(remote_cmd):
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "raspberry@192.168.138.141",
        remote_cmd
    ]
    
    print(f"[RunOnPi] Running: {remote_cmd}")
    
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
                    os.write(fd, b"1111\n")
                    password_sent = True
                    buffer = b""
            except OSError:
                break
                
        _, status = os.waitpid(pid, 0)
        exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
        return exit_code

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 run_on_pi.py <command>")
        sys.exit(1)
    
    remote_cmd = " ".join(sys.argv[1:])
    sys.exit(run_command(remote_cmd))
