#!/usr/bin/env python3
"""
Desktop Agent Template Signing
Signs YAML templates with Ed25519 digital signatures
"""

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


def load_private_key(key_path: str) -> tuple[ed25519.Ed25519PrivateKey, str]:
    """Load private key and extract key ID from filename"""
    key_file = Path(key_path)

    if not key_file.exists():
        raise FileNotFoundError(f"Private key not found: {key_path}")

    # Extract key ID from filename (remove .private.pem)
    key_id = key_file.stem.replace('.private', '')

    with open(key_file, 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None
        )

    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("Key must be Ed25519 private key")

    return private_key, key_id


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of template file"""
    with open(file_path, 'rb') as f:
        content = f.read()

    return hashlib.sha256(content).hexdigest()


def sign_template(template_path: str, private_key_path: str, output_path: str = None) -> dict:
    """Sign a template file and create signature sidecar"""

    template_file = Path(template_path)
    if not template_file.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    # Load private key
    private_key, key_id = load_private_key(private_key_path)

    # Calculate file hash
    file_hash = calculate_file_hash(template_path)

    # Create signature payload
    created_at = datetime.now().isoformat() + "+09:00"

    # What we actually sign: key_id + file_hash + created_at
    signature_payload = f"{key_id}:{file_hash}:{created_at}".encode('utf-8')

    # Generate signature
    signature_bytes = private_key.sign(signature_payload)
    signature_b64 = base64.b64encode(signature_bytes).decode('ascii')

    # Create signature sidecar
    signature_data = {
        "algo": "ed25519",
        "key_id": key_id,
        "created_at": created_at,
        "sha256": file_hash,
        "signature": signature_b64,
        "template_path": str(template_file.name)
    }

    # Determine output path
    if output_path is None:
        output_path = str(template_file.with_suffix(template_file.suffix + '.sig.json'))

    # Write signature file
    with open(output_path, 'w') as f:
        json.dump(signature_data, f, indent=2)

    print("✅ Template signed successfully:")
    print(f"   Template: {template_path}")
    print(f"   Key ID: {key_id}")
    print(f"   SHA-256: {file_hash}")
    print(f"   Signature: {output_path}")
    print(f"   Created: {created_at}")

    return signature_data


def batch_sign_templates(template_dir: str, private_key_path: str, pattern: str = "*.yaml") -> list:
    """Sign multiple templates in a directory"""

    template_path = Path(template_dir)
    if not template_path.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    templates = list(template_path.glob(pattern))
    if not templates:
        print(f"⚠️  No templates found matching pattern: {pattern}")
        return []

    results = []

    print(f"📝 Found {len(templates)} templates to sign...")

    for template_file in templates:
        # Skip already signed files and signature files
        if '.sig.json' in str(template_file):
            continue

        try:
            signature_data = sign_template(str(template_file), private_key_path)
            results.append({
                "template": str(template_file),
                "signature": signature_data,
                "status": "success"
            })
            print()

        except Exception as e:
            error_result = {
                "template": str(template_file),
                "status": "error",
                "error": str(e)
            }
            results.append(error_result)
            print(f"❌ Failed to sign {template_file}: {e}")

    success_count = len([r for r in results if r["status"] == "success"])
    error_count = len([r for r in results if r["status"] == "error"])

    print("\n📊 Batch signing complete:")
    print(f"   ✅ Signed: {success_count}")
    print(f"   ❌ Failed: {error_count}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Sign Desktop Agent templates with Ed25519 signatures"
    )
    parser.add_argument(
        "template",
        help="Template file or directory to sign"
    )
    parser.add_argument(
        "private_key",
        help="Path to private key file (.private.pem)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output signature file path (default: <template>.sig.json)"
    )
    parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="Batch mode: sign all templates in directory"
    )
    parser.add_argument(
        "--pattern", "-p",
        default="*.yaml",
        help="File pattern for batch mode (default: *.yaml)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing signature files"
    )

    args = parser.parse_args()

    try:
        if args.batch:
            # Batch signing mode
            results = batch_sign_templates(args.template, args.private_key, args.pattern)

            # Summary
            if results:
                failed = [r for r in results if r["status"] == "error"]
                if failed:
                    print(f"\n❌ {len(failed)} templates failed to sign:")
                    for result in failed:
                        print(f"   - {result['template']}: {result['error']}")
                    sys.exit(1)
                else:
                    print(f"\n🎉 All {len(results)} templates signed successfully!")

        else:
            # Single template signing
            template_path = Path(args.template)

            # Check if signature already exists
            if args.output:
                signature_path = Path(args.output)
            else:
                signature_path = template_path.with_suffix(template_path.suffix + '.sig.json')

            if signature_path.exists() and not args.force:
                print(f"❌ Signature already exists: {signature_path}")
                print("   Use --force to overwrite")
                sys.exit(1)

            _ = sign_template(args.template, args.private_key, args.output)

            print("\n🎉 Template signing complete!")

            # Verification hint
            print("\n💡 Verify signature with:")
            print(f"   python scripts/da_verify.py {args.template}")

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
