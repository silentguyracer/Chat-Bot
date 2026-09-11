import base64
from typing import Dict, Any, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class SSHKeyManager:
    """
    Manages generation, serialization, and export of SSH Ed25519 and RSA keypairs.
    """

    @staticmethod
    def generate_ed25519_keypair(comment: str = "chatbot-ssh-client") -> Dict[str, str]:
        """
        Generate a modern, high-security Ed25519 SSH keypair.
        Returns {'private_key': OpenSSH PEM string, 'public_key': OpenSSH public key string}.
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        # Serialize Private Key in OpenSSH format
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Serialize Public Key in OpenSSH format
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )

        return {
            "key_type": "ssh-ed25519",
            "private_key": private_bytes.decode("utf-8"),
            "public_key": f"{public_bytes.decode('utf-8')} {comment}".strip()
        }

    @staticmethod
    def generate_rsa_keypair(key_size: int = 4096, comment: str = "chatbot-rsa-client") -> Dict[str, str]:
        """Generate a 4096-bit RSA SSH keypair."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size
        )
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption()
        )

        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )

        return {
            "key_type": "ssh-rsa",
            "key_size": key_size,
            "private_key": private_bytes.decode("utf-8"),
            "public_key": f"{public_bytes.decode('utf-8')} {comment}".strip()
        }


class SSHCryptographicSigner:
    """
    Handles asymmetric message signing and verification using Ed25519 SSH keys.
    Prevents tampering, man-in-the-middle attacks, and unauthorized payload modifications.
    """

    @staticmethod
    def sign_message(private_key_pem: str, message_bytes: bytes) -> str:
        """
        Sign message bytes using Ed25519 private key.
        Returns base64-encoded signature string.
        """
        private_key = serialization.load_ssh_private_key(
            private_key_pem.encode("utf-8"),
            password=None
        )
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise ValueError("Only Ed25519 keys are supported for cryptographic message signing.")

        signature = private_key.sign(message_bytes)
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def verify_message(public_key_openssh: str, message_bytes: bytes, signature_b64: str) -> bool:
        """
        Verify message signature against OpenSSH formatted public key.
        Returns True if signature is valid, False otherwise.
        """
        try:
            public_key = serialization.load_ssh_public_key(
                public_key_openssh.encode("utf-8")
            )
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                return False

            signature = base64.b64decode(signature_b64.strip())
            public_key.verify(signature, message_bytes)
            return True
        except (InvalidSignature, ValueError, Exception):
            return False


class SSHTunnelHelper:
    """Helper for generating SSH port forwarding and secure tunnel commands."""

    @staticmethod
    def get_forward_tunnel_command(
        remote_user: str = "ubuntu",
        remote_host: str = "your-server-ip.com",
        local_port: int = 8000,
        remote_port: int = 8000,
        identity_file: str = "~/.ssh/id_ed25519"
    ) -> str:
        """Generate command to securely forward local web port to remote server over SSH."""
        return f"ssh -N -L {local_port}:localhost:{remote_port} -i {identity_file} {remote_user}@{remote_host}"

    @staticmethod
    def get_reverse_tunnel_command(
        remote_user: str = "ubuntu",
        remote_host: str = "your-server-ip.com",
        remote_port: int = 8000,
        local_port: int = 8000,
        identity_file: str = "~/.ssh/id_ed25519"
    ) -> str:
        """Generate reverse tunnel command (e.g. expose local dev chatbot securely to internet)."""
        return f"ssh -N -R {remote_port}:localhost:{local_port} -i {identity_file} {remote_user}@{remote_host}"
