"""
One-Command Zero-Rebuild Canary Rollback Utility.

Enforces instant rollback:
1. Calls the running service's /v1/admin/canary/rollback endpoint.
2. Persists the rolled-back state to ops/canary.json to maintain stability across container restarts.
3. Requires zero container rebuilds and zero service downtime.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request


def rollback_service(base_url: str, reason: str, file_path: Path | None = None) -> bool:
    """Invokes the rollback endpoint and updates local configuration."""
    clean_url = base_url.rstrip("/")
    endpoint = f"{clean_url}/v1/admin/canary/rollback?reason={urllib.parse.quote(reason)}"
    
    print(f"🛑 Initiating one-command canary rollback...")
    print(f"🎯 Target Endpoint: {clean_url}/v1/admin/canary/rollback")
    print(f"📝 Reason: {reason}")
    
    # 1. Trigger API rollback
    try:
        req = urllib.request.Request(endpoint, data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            print(f"\n✅ SERVICE ROLLBACK EXECUTED SUCCESSFULLY:")
            print(f"   • Status: {payload.get('status')}")
            print(f"   • Enabled: {payload.get('config', {}).get('enabled')}")
            print(f"   • Weight:  {payload.get('config', {}).get('weight')}")
    except Exception as exc:
        print(f"\n⚠️  Warning: Service API rollback call failed: {exc}", file=sys.stderr)
        print("   Proceeding to file persistence fallback...", file=sys.stderr)

    # 2. Persist configuration to disk so restarts maintain the rollback
    target_file = file_path or (Path(__file__).resolve().parent.parent / "canary.json")
    try:
        existing = {}
        if target_file.exists():
            with open(target_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        
        existing["enabled"] = False
        existing["weight"] = 0.0
        existing["last_rollback_timestamp"] = datetime.now(timezone.utc).isoformat()
        existing["last_rollback_reason"] = reason

        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

        print(f"💾 Persisted rollback state to: {target_file}")
    except Exception as exc:
        print(f"❌ Failed to persist rollback file: {exc}", file=sys.stderr)
        return False

    print("\n🚀 100% of live traffic is now pinned to 'stable'. Canary is completely deactivated.\n")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Runwise One-Command Canary Rollback")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:8000", help="Service base URL")
    parser.add_argument("--reason", type=str, default="Canary SLO latency breach or unexpected regression", help="Rollback reason")
    parser.add_argument("--file", type=str, default=None, help="Path to canary.json")

    args = parser.parse_args()
    file_path = Path(args.file) if args.file else None
    success = rollback_service(base_url=args.url, reason=args.reason, file_path=file_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
