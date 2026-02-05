"""Authentication module for the web interface."""

import secrets
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..helpers import Config

security = HTTPBasic()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def is_auth_configured(config: Config) -> bool:
    """Check if authentication is configured."""
    return bool(config.web_username and config.web_password_hash)


def get_config_dependency():
    """Factory to create config dependency with data_dir."""
    from .api import get_config
    return get_config


def verify_credentials(
    credentials: HTTPBasicCredentials = Depends(security),
    config: Config = Depends(lambda: None),  # Will be overridden
) -> str:
    """Verify HTTP Basic Auth credentials."""
    # This will be called with actual config from the route
    if not is_auth_configured(config):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication not configured. Please set up credentials first.",
        )
    
    username_correct = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        config.web_username.encode("utf-8"),
    )
    password_correct = verify_password(credentials.password, config.web_password_hash)
    
    if not (username_correct and password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return credentials.username


class AuthManager:
    """Manages authentication for the web interface."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def is_configured(self) -> bool:
        """Check if auth is configured."""
        return is_auth_configured(self.config)
    
    def setup(self, username: str, password: str) -> bool:
        """Set up authentication credentials."""
        if not username or not password:
            return False
        
        self.config.web_username = username
        self.config.web_password_hash = hash_password(password)
        self.config.save()
        return True
    
    def verify(self, credentials: HTTPBasicCredentials) -> bool:
        """Verify credentials."""
        if not self.is_configured():
            return False
        
        username_correct = secrets.compare_digest(
            credentials.username.encode("utf-8"),
            self.config.web_username.encode("utf-8"),
        )
        password_correct = verify_password(
            credentials.password, self.config.web_password_hash
        )
        
        return username_correct and password_correct
    
    def change_password(self, old_password: str, new_password: str) -> bool:
        """Change the password if old password is correct."""
        if not verify_password(old_password, self.config.web_password_hash):
            return False
        
        self.config.web_password_hash = hash_password(new_password)
        self.config.save()
        return True
