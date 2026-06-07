import socket
import threading
import sys
import os
import datetime

from crypto_utils import (
    send_framed_msg, recv_framed_msg,
    generate_dh_keypair, derive_shared_key,
    encrypt_message, decrypt_message
)

HOST = "127.0.0.1"
PORT = 5000
log_lock = threading.Lock()

# =========================
# LOCAL LOGGING
# =========================
def log_client_event(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_lock:
        with open("logs/client.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

# =========================
# BACKGROUND RECEIVER
# =========================
def receive_handler(sock, shared_key):
    try:
        while True:
            encrypted_bytes = recv_framed_msg(sock)
            if not encrypted_bytes:
                print("\n[-] Connection lost to server.")
                break

            # Decrypt payload using AES-GCM
            decrypted_text = decrypt_message(shared_key, encrypted_bytes)
            log_client_event(f"Received message: {decrypted_text}")

            # Clear current input prompt visual dynamically
            print(f"\r[Peer]: {decrypted_text}\n[You]: ", end="", flush=True)
    except Exception as e:
        log_client_event(f"Error in receiver loop: {e}")
    finally:
        print("\n[-] Exiting receiver loop.")

# =========================
# MAIN APP FLOW
# =========================
def start_client():
    os.makedirs("logs", exist_ok=True)

    room_id = input("[*] Enter Room ID to join/create: ").strip()
    if not room_id:
        print("[-] Invalid Room ID.")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
        print(f"[+] Connected to server at {HOST}:{PORT}")
    except Exception as e:
        print(f"[-] Connection failed: {e}")
        return

    try:
        # Step 1: Send Room Identification Packet
        send_framed_msg(sock, f"join_room:{room_id}".encode())
        print("[*] Handshake sent. Waiting for a peer to join your room...")

        # Step 2: Block until server pairs two clients
        status = recv_framed_msg(sock)
        if status == b"error:room_full":
            print("[-] This room is currently occupied (Max 2 peers).")
            sock.close()
            return

        if status != b"peer_ready":
            print("[-] Unexpected initialization breakdown from server.")
            sock.close()
            return

        print("[+] Peer connected! Initializing E2EE cryptographic key exchange...")
        log_client_event(f"Room '{room_id}' matched. Initializing key exchange.")

        # Step 3: Diffie-Hellman Key Exchange (X25519)
        priv_key, pub_key = generate_dh_keypair()
        my_public_bytes = pub_key.public_bytes_raw()

        # Transmit raw public bytes to peer via server relay
        send_framed_msg(sock, my_public_bytes)

        # Receive peer's raw public bytes
        peer_public_bytes = recv_framed_msg(sock)
        if not peer_public_bytes:
            print("[-] Peer disconnected during key exchange.")
            return

        # Derive symmetric shared encryption key
        shared_key = derive_shared_key(priv_key, peer_public_bytes)
        print("[+] Secure End-to-End Encryption established!")
        log_client_event("Shared key successfully derived via HKDF-SHA256.")

        # Step 4: Run asynchronous background receiver thread
        receiver_thread = threading.Thread(target=receive_handler, args=(sock, shared_key), daemon=True)
        receiver_thread.start()

        # Step 5: Main User Transmission Loop
        print("\n--- Start Chatting (Press Ctrl+C or type 'exit' to quit) ---")
        while True:
            msg = input("[You]: ").strip()
            if msg.lower() == 'exit':
                break
            if not msg:
                continue

            # Encrypt message string to safe Nonce + Ciphertext payload
            encrypted_payload = encrypt_message(shared_key, msg)
            log_client_event(f"Sent message: {msg}")
            send_framed_msg(sock, encrypted_payload)

    except KeyboardInterrupt:
        print("\n[*] Disconnecting chat session.")
    except Exception as e:
        print(f"\n[!] Client exception encountered: {e}")
    finally:
        sock.close()
        print("[-] Connection terminated safely.")

if __name__ == "__main__":
    start_client()
