#!/usr/bin/env python3
"""
Desktop Agent Template Verification
Verifies Ed25519 digital signatures on YAML templates
"""

import argparse
import base64
import hashlib
import json
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature


class TemplateVerificationError(Exception):
    """Template verification failed"""
    pass


class TrustStore:
    """Manages trusted public keys for signature verification"""
    
    def __init__(self, trust_store_path: str = "configs/trust_store.yaml"):
        self.trust_store_path = Path(trust_store_path)
        self.keys = {}
        self.load_trust_store()
    
    def load_trust_store(self):
        """Load trusted keys from trust store file"""
        if not self.trust_store_path.exists():
            print(f"⚠️  Trust store not found: {self.trust_store_path}")
            return
        
        try:
            with open(self.trust_store_path, 'r') as f:
                trust_data = yaml.safe_load(f) or {}
            
            keys_data = trust_data.get('keys', [])
            for key_data in keys_data:
                key_id = key_data.get('key_id')
                pubkey_b64 = key_data.get('pubkey')
                
                if key_id and pubkey_b64:
                    try:
                        # Decode base64 public key
                        pubkey_bytes = base64.b64decode(pubkey_b64)
                        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pubkey_bytes)
                        
                        self.keys[key_id] = {
                            'public_key': public_key,
                            'created_at': key_data.get('created_at'),
                            'pubkey_b64': pubkey_b64
                        }
                        
                    except Exception as e:
                        print(f"⚠️  Invalid public key for {key_id}: {e}")
            
            print(f"🔑 Loaded {len(self.keys)} trusted keys from trust store")
            
        except Exception as e:
            print(f"⚠️  Failed to load trust store: {e}")
    
    def get_public_key(self, key_id: str) -> Optional[ed25519.Ed25519PublicKey]:
        """Get public key by key ID"""
        key_data = self.keys.get(key_id)
        return key_data['public_key'] if key_data else None
    
    def is_trusted(self, key_id: str) -> bool:
        """Check if key ID is in trust store"""
        return key_id in self.keys
    
    def list_keys(self):
        """List all trusted keys"""
        for key_id, key_data in self.keys.items():
            print(f"  📍 {key_id}")
            print(f"     Created: {key_data.get('created_at', 'Unknown')}")
            print(f"     Pubkey: {key_data['pubkey_b64'][:32]}...")


class PolicyManager:
    """Manages signature verification policies"""
    
    def __init__(self, policy_path: str = "configs/policy.yaml"):
        self.policy_path = Path(policy_path)
        self.policy = self.load_policy()
    
    def load_policy(self) -> Dict[str, Any]:
        """Load verification policy"""
        if not self.policy_path.exists():
            # Default policy
            return {
                "require_signed_templates": True,
                "trusted_authors": [],
                "allow_unsigned_until": None
            }
        
        try:
            with open(self.policy_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"⚠️  Failed to load policy: {e}")
            return {}
    
    def requires_signature(self) -> bool:
        """Check if signatures are required by policy"""
        return self.policy.get("require_signed_templates", True)
    
    def is_author_trusted(self, key_id: str) -> bool:
        """Check if author is in trusted authors list"""
        trusted_authors = self.policy.get("trusted_authors", [])
        return key_id in trusted_authors
    
    def is_unsigned_allowed(self) -> bool:
        """Check if unsigned templates are still allowed (grace period)"""
        if not self.policy.get("require_signed_templates", True):
            return True
        
        allow_until = self.policy.get("allow_unsigned_until")
        if not allow_until:
            return False
        
        from datetime import datetime
        try:
            deadline = datetime.fromisoformat(allow_until.replace('Z', '+00:00'))
            return datetime.now() < deadline
        except Exception:
            return False


def load_signature_file(signature_path: str) -> Dict[str, Any]:
    """Load signature sidecar file"""
    with open(signature_path, 'r') as f:
        return json.load(f)


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of file"""
    with open(file_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def verify_template_signature(template_path: str, trust_store: TrustStore, policy: PolicyManager) -> Dict[str, Any]:
    """Verify template signature and return verification result"""
    
    template_file = Path(template_path)
    signature_file = template_file.with_suffix(template_file.suffix + '.sig.json')
    
    result = {
        "template_path": str(template_file),
        "signature_path": str(signature_file),
        "verified": False,
        "trusted": False,
        "error": None,
        "signature_data": None,
        "policy_compliant": False
    }
    
    # Check if signature file exists
    if not signature_file.exists():
        if policy.is_unsigned_allowed():
            result["error"] = "No signature found (allowed by grace period)"
            result["policy_compliant"] = True
            return result
        else:
            result["error"] = "No signature file found and signatures are required"
            return result
    
    try:
        # Load signature
        signature_data = load_signature_file(str(signature_file))
        result["signature_data"] = signature_data
        
        # Verify hash
        current_hash = calculate_file_hash(template_path)
        stored_hash = signature_data.get("sha256")
        
        if current_hash != stored_hash:
            result["error"] = f"Hash mismatch: expected {stored_hash}, got {current_hash}"
            return result
        
        # Get signing key
        key_id = signature_data.get("key_id")
        if not key_id:
            result["error"] = "No key_id in signature"
            return result
        
        public_key = trust_store.get_public_key(key_id)
        if not public_key:
            result["error"] = f"Key not found in trust store: {key_id}"
            return result
        
        # Verify signature
        signature_b64 = signature_data.get("signature")
        if not signature_b64:
            result["error"] = "No signature data"
            return result
        
        try:
            signature_bytes = base64.b64decode(signature_b64)
        except Exception as e:
            result["error"] = f"Invalid signature encoding: {e}"
            return result
        
        # Reconstruct signed payload
        created_at = signature_data.get("created_at")
        signature_payload = f"{key_id}:{stored_hash}:{created_at}".encode('utf-8')
        
        try:
            public_key.verify(signature_bytes, signature_payload)
            result["verified"] = True
        except InvalidSignature:
            result["error"] = "Invalid signature"
            return result
        
        # Check if key is trusted
        result["trusted"] = trust_store.is_trusted(key_id)
        
        # Check policy compliance
        if policy.requires_signature():
            if result["verified"] and (result["trusted"] or policy.is_author_trusted(key_id)):
                result["policy_compliant"] = True
            else:
                result["error"] = f"Policy violation: untrusted author {key_id}"
        else:
            result["policy_compliant"] = True
        
    except Exception as e:
        result["error"] = f"Verification error: {e}"
    
    return result


def verify_batch_templates(template_dir: str, pattern: str = "*.yaml") -> Dict[str, Any]:
    """Verify multiple templates in directory"""
    
    trust_store = TrustStore()
    policy = PolicyManager()
    
    template_path = Path(template_dir)
    templates = list(template_path.glob(pattern))
    
    if not templates:
        return {
            "total": 0,
            "verified": 0,
            "failed": 0,
            "results": []
        }
    
    results = []
    verified_count = 0
    failed_count = 0
    
    for template_file in templates:
        # Skip signature files
        if '.sig.json' in str(template_file):
            continue
        
        result = verify_template_signature(str(template_file), trust_store, policy)
        results.append(result)
        
        if result["verified"] and result["policy_compliant"]:
            verified_count += 1
        else:
            failed_count += 1
    
    return {
        "total": len(results),
        "verified": verified_count,
        "failed": failed_count,
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(
        description="Verify Desktop Agent template signatures"
    )
    parser.add_argument(
        "template",
        help="Template file or directory to verify"
    )
    parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="Batch mode: verify all templates in directory"
    )
    parser.add_argument(
        "--pattern", "-p",
        default="*.yaml",
        help="File pattern for batch mode (default: *.yaml)"
    )
    parser.add_argument(
        "--trust-store", "-t",
        default="configs/trust_store.yaml",
        help="Path to trust store file"
    )
    parser.add_argument(
        "--policy", "-pol",
        default="configs/policy.yaml",
        help="Path to policy file"
    )
    parser.add_argument(
        "--list-keys", "-l",
        action="store_true",
        help="List trusted keys and exit"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        trust_store = TrustStore(args.trust_store)
        policy = PolicyManager(args.policy)
        
        if args.list_keys:
            print("🔑 Trusted keys in trust store:")
            if not trust_store.keys:
                print("  (none)")
            else:
                trust_store.list_keys()
            return
        
        if args.batch:
            # Batch verification
            print(f"🔍 Verifying templates in: {args.template}")
            results = verify_batch_templates(args.template, args.pattern)
            
            print(f"\n📊 Verification Summary:")
            print(f"   Total templates: {results['total']}")
            print(f"   ✅ Verified: {results['verified']}")
            print(f"   ❌ Failed: {results['failed']}")
            
            if args.verbose or results['failed'] > 0:
                print(f"\n📋 Detailed Results:")
                for result in results['results']:
                    status = "✅" if (result['verified'] and result['policy_compliant']) else "❌"
                    template_name = Path(result['template_path']).name
                    print(f"   {status} {template_name}")
                    
                    if result['error']:
                        print(f"      Error: {result['error']}")
                    elif result['signature_data']:
                        sig_data = result['signature_data']
                        print(f"      Signed by: {sig_data.get('key_id')}")
                        print(f"      Created: {sig_data.get('created_at')}")
            
            if results['failed'] > 0:
                sys.exit(1)
            
        else:
            # Single template verification
            result = verify_template_signature(args.template, trust_store, policy)
            
            print(f"🔍 Verifying: {result['template_path']}")
            
            if result['verified'] and result['policy_compliant']:
                print("✅ Verification successful!")
                sig_data = result['signature_data']
                print(f"   Signed by: {sig_data.get('key_id')}")
                print(f"   Created: {sig_data.get('created_at')}")
                print(f"   SHA-256: {sig_data.get('sha256')}")
                print(f"   Trusted: {'Yes' if result['trusted'] else 'No'}")
            else:
                print("❌ Verification failed!")
                print(f"   Error: {result.get('error', 'Unknown error')}")
                sys.exit(1)
    
    except KeyboardInterrupt:
        print(f"\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()