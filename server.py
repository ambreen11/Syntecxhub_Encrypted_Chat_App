import socket
import threading
import os
import datetime

from crypto_utils import recv_framed_msg, send_framed_msg

HOST = "127.0.0.1"
PORT = 5000

# room_id -> list of client connections
rooms = {}
lock = threading.Lock()
log_lock = threading.Lock()

# =========================
# THREAD-SAFE LOGGING
# =========================
def log_event(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)

    with log_lock:
        with open("logs/server.log", "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")

# =========================
# MESSAGE RELAY
# =========================
def broadcast(room_id, data, sender):
    with lock:
        if room_id not in rooms:
            return

        for client in rooms[room_id][:]:
            if client != sender:
                try:
                    send_framed_msg(client, data)
                except:
                    try:
                        client.close()
                    except:
                        pass
                    if client in rooms[room_id]:
                        rooms[room_id].remove(client)

        if len(rooms[room_id]) == 0:
            del rooms[room_id]

# =========================
# CLIENT HANDLER
# =========================
def handle_client(conn, addr):
    room_id = None
    log_event(f"New connection from {addr}")

    try:
        # -------------------------
        # STEP 1: JOIN ROOM
        # -------------------------
        join = recv_framed_msg(conn)
        if not join or not join.startswith(b"join_room:"):
            conn.close()
            return

        room_id = join.split(b":", 1)[1].decode().strip()
        if not room_id:
            conn.close()
            return

        with lock:
            rooms.setdefault(room_id, [])
            # Enforce max 2 clients per room for E2EE P2P mapping
            if len(rooms[room_id]) >= 2:
                send_framed_msg(conn, b"error:room_full")
                conn.close()
                return
            rooms[room_id].append(conn)
            room_size = len(rooms[room_id])

        log_event(f"{addr} successfully joined room '{room_id}'")

        # -------------------------
        # STEP 2: NOTIFY PEERS TO START KEY EXCHANGE
        # -------------------------
        if room_size == 2:
            log_event(f"Room '{room_id}' is now full. Triggering Key Exchange.")
            with lock:
                for c in rooms[room_id]:
                    try:
                        send_framed_msg(c, b"peer_ready")
                    except:
                        pass

        # -------------------------
        # STEP 3: MAIN RECEIVE AND RELAY LOOP
        # -------------------------
        while True:
            data = recv_framed_msg(conn)
            if not data:
                break

            log_event(f"Relaying {len(data)} encrypted bytes from {addr} in room '{room_id}'")
            broadcast(room_id, data, conn)

    except Exception as e:
        log_event(f"Error handling client {addr}: {e}")

    finally:
        # -------------------------
        # CLEANUP
        # -------------------------
        with lock:
            if room_id in rooms:
                if conn in rooms[room_id]:
                    rooms[room_id].remove(conn)
                if len(rooms[room_id]) == 0:
                    del rooms[room_id]

        try:
            conn.close()
        except:
            pass
        log_event(f"Client {addr} disconnected from room '{room_id}'")

# =========================
# SERVER START
# =========================
def start_server():
    os.makedirs("logs", exist_ok=True)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(50)

    log_event(f"Server running on {HOST}:{PORT}. Waiting for clients...")

    try:
        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True
            ).start()
    except KeyboardInterrupt:
        log_event("Server shutting down.")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()
