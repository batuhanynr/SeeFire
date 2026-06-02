#!/usr/bin/env python3
import os
import pty
import sys
import time

def main():
    # command to run
    cmd = [
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "interactive_ride_test.py",
        "raspberry@192.168.138.141:~/SeeFire/"
    ]
    
    print(f"Spawning: {' '.join(cmd)}")
    
    # Spawn in pseudo-terminal
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process: execute scp
        os.execvp(cmd[0], cmd)
    else:
        # Parent process: monitor output and feed password
        password_sent = False
        buffer = b""
        
        while True:
            try:
                # Read output from child
                data = os.read(fd, 1024)
                if not data:
                    break
                
                buffer += data
                sys.stdout.buffer.write(data)
                sys.stdout.flush()
                
                # Check if it asks for password
                if b"password:" in buffer.lower() and not password_sent:
                    print("\n[Script] Sending password...")
                    os.write(fd, b"1111\n")
                    password_sent = True
                    buffer = b"" # clear buffer
                    
            except OSError:
                break
                
        # Wait for child to exit
        _, status = os.waitpid(pid, 0)
        exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
        print(f"\n[Script] Complete. Exit code: {exit_code}")
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
