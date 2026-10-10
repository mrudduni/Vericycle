"""Signatures over event hashes.

KMS signs with ``MessageType="DIGEST"`` and ``ECDSA_SHA_256`` on an ``ECC_NIST_P256`` key,
which is ECDSA over the 32-byte hash treated as a pre-computed SHA-256 digest.
Verification is local with ``cryptography`` once the public key is fetched (``GetPublicKey``).
``LocalSigner`` produces byte-compatible signatures for offline tests and seeding dry runs.
"""
from __future__ import annotations

import base64
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

_ALGO = ec.ECDSA(Prehashed(hashes.SHA256()))


class Signer(Protocol):
    def sign(self, hash_hex: str) -> str: """Return a base64 DER ECDSA signature over bytes.fromhex(hash_hex)."""
    def public_key_pem(self) -> str: ...


class LocalSigner:
    """In-process P-256 key. For tests only; production signs in KMS."""

    def __init__(self, private_key: ec.EllipticCurvePrivateKey | None = None):
        self._key = private_key or ec.generate_private_key(ec.SECP256R1())

    def sign(self, hash_hex: str) -> str:
        return base64.b64encode(self._key.sign(bytes.fromhex(hash_hex), _ALGO)).decode("ascii")

    def public_key_pem(self) -> str:
        return self._key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("ascii")


def load_public_key(pem_or_der: str | bytes) -> ec.EllipticCurvePublicKey:
    if isinstance(pem_or_der, str):
        pem_or_der = pem_or_der.encode("ascii")
    if pem_or_der.lstrip().startswith(b"-----BEGIN"):
        key = serialization.load_pem_public_key(pem_or_der)
    else:  # KMS GetPublicKey returns DER SubjectPublicKeyInfo
        key = serialization.load_der_public_key(pem_or_der)
    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise ValueError("ledger signing key must be an EC public key")
    return key


def der_to_pem(der: bytes) -> str:
    return load_public_key(der).public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")


def verify_signature(public_key: ec.EllipticCurvePublicKey, hash_hex: str, sig_b64: str) -> bool:
    try:
        public_key.verify(base64.b64decode(sig_b64, validate=True), bytes.fromhex(hash_hex), _ALGO)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
