from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Annotated, Optional
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.constants import (
    ADMIN_ONLY_METHODS,
    AUDIT_LOG_PATH,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    TOKEN_LIFETIME_MINUTES,
)

BEARER = HTTPBearer(auto_error=False)


class AccessControl:
    """JWT issue/verify, role-based authorization and audit logging."""

    def __init__(self):
        self.secret_key = os.environ.get("LOANSERVE_JWT_SECRET", JWT_SECRET_KEY)
        self.open_mode = os.environ.get("LOANSERVE_OPEN_MODE") == "1"

    def issue_token(self, user_name, role):
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=TOKEN_LIFETIME_MINUTES)
        claims = {
            "sub": user_name,
            "role": role,
            "exp": int(exp.timestamp()),
        }
        return jwt.encode(claims, self.secret_key, algorithm=JWT_ALGORITHM)

    def read_token(self, authorization_header):
        if not authorization_header or not authorization_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="A bearer token is required in Authorization header",
            )

        token = authorization_header[len("Bearer ") :].strip()
        try:
            return jwt.decode(token, self.secret_key, algorithms=[JWT_ALGORITHM])
        except Exception as exc:
            raise HTTPException(
                status_code=401,
                detail=f"Invalid or expired token: {exc}",
            ) from exc

    def authorise(
        self,
        request: Request,
        offered: Annotated[Optional[HTTPAuthorizationCredentials], Depends(BEARER)] = None,
    ):
        header = request.headers.get("Authorization", "")
        claims = self.read_token(header)

        if request.method in ADMIN_ONLY_METHODS and claims.get("role") != "administrator":
            raise HTTPException(
                status_code=403,
                detail=f"Role '{claims.get('role')}' is not permitted to perform {request.method}",
            )

        return claims

    def record_audit_entry(self, user_name, action):
        path_str = os.environ.get("LOANSERVE_AUDIT_LOG", AUDIT_LOG_PATH)
        audit_path = Path(path_str)
        audit_path.parent.mkdir(parents=True, exist_ok=True)

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        line = f"{now_str} {user_name} {action}\n"
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(line)


if __name__ == "__main__":
    ac = AccessControl()
    token = ac.issue_token("priya", "administrator")
    claims = ac.read_token(f"Bearer {token}")
    print(claims)
