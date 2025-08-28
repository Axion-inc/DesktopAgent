#!/usr/bin/env python3
"""
Desktop Agent Template Signing - Key Generation
Generates Ed25519 key pairs for template signing and verification
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


def generate_keypair(key_id: str, output_dir: str = "keys") -> dict:
    """Generate Ed25519 key pair for template signing"""

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Generate private key
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Serialize keys
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Get raw public key bytes for trust store
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    # Create key metadata
    created_at = datetime.now().isoformat() + "+09:00"

    # Save private key
    private_key_path = output_path / f"{key_id}.private.pem"
    with open(private_key_path, 'wb') as f:
        f.write(private_pem)

    # Set restrictive permissions on private key
    os.chmod(private_key_path, 0o600)

    # Save public key
    public_key_path = output_path / f"{key_id}.public.pem"
    with open(public_key_path, 'wb') as f:
        f.write(public_pem)

    # Create trust store entry
    trust_entry = {
        "key_id": key_id,
        "pubkey": base64.b64encode(public_raw).decode('ascii'),
        "created_at": created_at,
        "algorithm": "ed25519",
        "purpose": "template_signing"
    }

    # Save trust store entry
    trust_entry_path = output_path / f"{key_id}.trust.json"
    with open(trust_entry_path, 'w') as f:
        json.dump(trust_entry, f, indent=2)

    print("✅ Generated Ed25519 key pair:")
    print(f"   Key ID: {key_id}")
    print(f"   Private key: {private_key_path}")
    print(f"   Public key: {public_key_path}")
    print(f"   Trust entry: {trust_entry_path}")
    print()
    print("🔐 Add this to configs/trust_store.yaml:")
    print(f"  - key_id: \"{key_id}\"")
    print(f"    pubkey: \"{trust_entry['pubkey']}\"")
    print(f"    created_at: \"{created_at}\"")
    print()
    print("⚠️  Keep the private key secure and backed up!")
    print(f"   Private key permissions: {oct(os.stat(private_key_path).st_mode)[-3:]}")

    return {
        "key_id": key_id,
        "private_key_path": str(private_key_path),
        "public_key_path": str(public_key_path),
        "trust_entry": trust_entry
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate Ed25519 key pair for Desktop Agent template signing"
    )
    parser.add_argument(
        "key_id",
        help="Key identifier (e.g., 'da:2025:alice', 'company:2025:teamname')"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="keys",
        help="Output directory for keys (default: keys/)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing keys"
    )

    args = parser.parse_args()

    # Validate key ID format
    if ":" not in args.key_id:
        print("❌ Error: Key ID should contain namespace (e.g., 'da:2025:alice')")
        sys.exit(1)

    # Check if key already exists
    output_path = Path(args.output_dir)
    private_key_path = output_path / f"{args.key_id}.private.pem"

    if private_key_path.exists() and not args.force:
        print(f"❌ Error: Key already exists: {private_key_path}")
        print("   Use --force to overwrite")
        sys.exit(1)

    try:
        result = generate_keypair(args.key_id, args.output_dir)

        # Optional: Update trust store automatically
        trust_store_path = Path("configs/trust_store.yaml")
        if trust_store_path.exists():
            response = input("\n🤔 Update configs/trust_store.yaml automatically? (y/N): ")
            if response.lower() == 'y':
                import yaml

                # Load existing trust store
                with open(trust_store_path, 'r') as f:
                    trust_store = yaml.safe_load(f) or {"keys": []}

                if "keys" not in trust_store:
                    trust_store["keys"] = []

                # Check if key already exists
                existing = next((k for k in trust_store["keys"] if k.get("key_id") == args.key_id), None)
                if existing:
                    trust_store["keys"].remove(existing)

                # Add new key
                trust_store["keys"].append({
                    "key_id": result["trust_entry"]["key_id"],
                    "pubkey": result["trust_entry"]["pubkey"],
                    "created_at": result["trust_entry"]["created_at"]
                })

                # Save updated trust store
                with open(trust_store_path, 'w') as f:
                    yaml.dump(trust_store, f, default_flow_style=False, sort_keys=False)

                print(f"✅ Updated {trust_store_path}")

        print("\n🎉 Key generation complete!")

    except Exception as e:
        print(f"❌ Error generating keys: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
