"""Encryption/decryption utilities for the AMG graph store.

Uses AES-256-GCM via the cryptography library.
Key is stored in macOS Keychain via the `security` CLI tool.
"""

from __future__ import annotations

import json
import os
import subprocess

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEYCHAIN_SERVICE = "adaptive-memory-graph"
KEYCHAIN_ACCOUNT = "amg-encryption-key"
KEY_LENGTH = 32  # 256 bits
NONCE_LENGTH = 12


def _keychain_get() -> bytes | None:
    """Retrieve the encryption key from macOS Keychain."""
    try:
        result = subprocess.run(
            [
                "security", "find-generic-password",
                "-s", KEYCHAIN_SERVICE,
                "-a", KEYCHAIN_ACCOUNT,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return bytes.fromhex(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None


def _keychain_set(key_hex: str) -> None:
    """Store the encryption key in macOS Keychain."""
    # Delete existing entry if present
    subprocess.run(
        [
            "security", "delete-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", KEYCHAIN_ACCOUNT,
        ],
        capture_output=True,
    )
    subprocess.run(
        [
            "security", "add-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", KEYCHAIN_ACCOUNT,
            "-w", key_hex,
            "-U",
        ],
        capture_output=True,
        check=True,
    )


def get_or_create_key() -> bytes:
    """Get the encryption key from Keychain, or generate and store a new one."""
    key = _keychain_get()
    if key and len(key) == KEY_LENGTH:
        return key
    # Generate a new key
    key = AESGCM.generate_key(bit_length=256)
    _keychain_set(key.hex())
    return key


def encrypt(data: dict, key: bytes) -> bytes:
    """Encrypt a dict as JSON using AES-256-GCM. Returns nonce + ciphertext."""
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    nonce = os.urandom(NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt(blob: bytes, key: bytes) -> dict:
    """Decrypt nonce + ciphertext back to a dict."""
    nonce = blob[:NONCE_LENGTH]
    ciphertext = blob[NONCE_LENGTH:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))
