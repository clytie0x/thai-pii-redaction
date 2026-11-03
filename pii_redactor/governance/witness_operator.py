"""Reference independent loopback witness, behind a separately accepted TLS proxy."""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pii_redactor.governance.checkpoints import Witness, witness_handler
from pii_redactor.governance.operator_files import create_private, read_private, require_private


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-file", required=True)
    parser.add_argument("--identity", action="store_true")
    args = parser.parse_args(argv)
    server = None
    try:
        config = read_private(args.config_file)
        if set(config) != {"organization", "signing_key_hex", "token", "store", "port"}:
            raise ValueError
        organization = str(UUID(config["organization"]))
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(config["signing_key_hex"]))
        if type(config["port"]) is not int or not 1024 <= config["port"] <= 65535:
            raise ValueError
        if not isinstance(config["token"], str) or not 32 <= len(config["token"]) <= 4096:
            raise ValueError
        if args.identity:
            print(
                json.dumps(
                    {
                        "organization": organization,
                        "public_key_hex": key.public_key()
                        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
                        .hex(),
                    }
                )
            )
            return 0
        path = Path(config["store"])
        if not path.is_absolute():
            raise ValueError
        if not path.exists():
            with create_private(path) as stream:
                stream.flush()
                os.fsync(stream.fileno())
        require_private(path)
        authority = Witness(path, key, organization_id=organization)
        server = ThreadingHTTPServer(
            ("127.0.0.1", config["port"]), witness_handler(authority, config["token"])
        )
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("witness_operation_failed", file=sys.stderr)
        return 1
    finally:
        if server:
            server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
