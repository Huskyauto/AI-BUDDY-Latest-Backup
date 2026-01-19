import socket

def check_port(port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0  # Return True if port is in use
    except Exception as e:
        print(f"Error checking port {port}: {e}")
        return False

print(f"Port 5000 in use: {check_port(5000)}")
print(f"Port 5001 in use: {check_port(5001)}")
print(f"Port 5002 in use: {check_port(5002)}")