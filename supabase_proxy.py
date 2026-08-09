import socket
import threading

def handle_client(client_sock, remote_host, remote_port):
    try:
        remote_sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        remote_sock.connect((remote_host, remote_port))
        
        def forward(src, dst, name):
            try:
                while True:
                    data = src.recv(4096)
                    if not data: break
                    print(f"{name} {len(data)} bytes: {data.hex()}")
                    dst.sendall(data)
            except Exception as e:
                print(f"Error in {name}: {e}")
            finally:
                src.close()
                dst.close()

        threading.Thread(target=forward, args=(client_sock, remote_sock, "C->S")).start()
        threading.Thread(target=forward, args=(remote_sock, client_sock, "S->C")).start()
    except Exception as e:
        print(f"Error connecting to remote: {e}")
        client_sock.close()

def main():
    local_host, local_port = '0.0.0.0', 5433
    remote_host, remote_port = 'db.mdvfvtpbwqhccmaarpli.supabase.co', 5432
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((local_host, local_port))
    server.listen(100)
    print(f"Proxying IPv4 {local_host}:{local_port} to IPv6 {remote_host}:{remote_port}")
    
    try:
        while True:
            client_sock, addr = server.accept()
            print(f"Accepted connection from {addr}")
            threading.Thread(target=handle_client, args=(client_sock, remote_host, remote_port)).start()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()

if __name__ == '__main__':
    main()
