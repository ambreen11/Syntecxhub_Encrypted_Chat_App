import struct
import os
from typing import Optional
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

def send_framed_msg(sock, data: bytes):
    """Prefixes message with a 4-byte big-endian length header."""
    length = len(data)
    packet = struct.pack('!I', length) + data
    sock.sendall(packet)

def recv_framed_msg(sock) -> Optional[bytes]:
    """Reads the 4-byte header, then reads the exact message payload."""
    try:
        header = sock.recv(4)
        if not header or len(header) < 4:
            return None
        length = struct.unpack('!I', header)[0]

        # Read exact payload size
        data = bytearray()
        while len(data) < length:
            packet = sock.recv(length - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)
    except:
        return None

def generate_dh_keypair():
    """Generates an X25519 private/public keypair."""
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key

def derive_shared_key(private_key, peer_public_bytes: bytes) -> bytes:
    """Derives a secure 32-byte AES key using HKDF from DH shared secret."""
    peer_public_key = x25519.X25519PublicKey.from_public_bytes(peer_public_bytes)
    shared_secret = private_key.exchange(peer_public_key)

    # Deriving 256-bit AES key
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'chat-e2ee-salt',
    ).derive(shared_secret)

def encrypt_message(key: bytes, message: str) -> bytes:
    """Encrypts plaintext string using AES-GCM."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, message.encode(), None)
    return nonce + ciphertext

def decrypt_message(key: bytes, data: bytes) -> str:
    """Decrypts AES-GCM ciphertext data to string."""
    aesgcm = AESGCM(key)
    nonce = data[:12]
    ciphertext = data[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()

def send_framed_msg(sock, data):
    length = struct.pack('!I', len(data))
    sock.sendall(length + data)

def recv_framed_msg(sock):
    raw_len = recvall(sock, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack('!I', raw_len)[0]
    return recvall(sock, msg_len)

def recvall(sock, n):
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data