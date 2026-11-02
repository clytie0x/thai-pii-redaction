"""Protected bounded operator files; no keys or DSNs in command arguments."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from pii_redactor.governance.errors import GovernanceError


def require_private(path):
    path = Path(path)
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)() or not path.exists():
        raise GovernanceError("operator_file_unprotected")
    if os.name == "nt":
        # Check SIDs, not localized account names. A protected inherited DACL is OK.
        script = (
            "$ErrorActionPreference='Stop'; $a=Get-Acl -LiteralPath $env:AIGUARD_ACL_PATH; "
            "$u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; "
            "$ok=@($u,'S-1-5-18','S-1-5-32-544'); "
            "if(@($a.Access).Count -eq 0){exit 1}; "
            "foreach($r in $a.Access){ if($r.AccessControlType -eq 'Allow'){ "
            "$s=$r.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value; "
            "if($s -notin $ok){exit 1}}}; if($a.Owner -eq $null){exit 1}; "
            "$o=([System.Security.Principal.NTAccount]$a.Owner).Translate([System.Security.Principal.SecurityIdentifier]).Value; "
            "if($o -notin $ok){exit 1}"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            env={
                **{k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"},
                "AIGUARD_ACL_PATH": str(path.resolve()),
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        if result.returncode:
            raise GovernanceError("operator_file_unprotected")
    elif path.stat().st_mode & 0o077:
        raise GovernanceError("operator_file_unprotected")
    return path


def read_private(path, *, limit=65536):
    try:
        file = require_private(path)
        with file.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError
        return json.loads(raw)
    except GovernanceError:
        raise
    except Exception:
        raise GovernanceError("operator_file_invalid") from None


def create_private(path):
    path = Path(path)
    require_private(path.parent)
    if path.exists() or path.is_symlink():
        raise GovernanceError("operator_target_exists")
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")
