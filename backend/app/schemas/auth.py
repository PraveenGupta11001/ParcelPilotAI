from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    """Pydantic schema representing user login credentials.

    Attributes:
        email: Registered account email address.
        password: User cleartext password for validation.
    """
    email: str
    password: str

class RegisterRequest(BaseModel):
    """Pydantic schema for creating a new user account.

    Attributes:
        full_name: The user's first and last name.
        email: Desired email address for login.
        password: Cleartext password to hash.
        role: Functional system role (customer, internal_support, internal_lead).
        account_id: Associated account scoped tracking ID, optional if internal staff.
    """
    full_name: str
    email: str
    password: str
    role: str  # customer, internal_support, internal_lead
    account_id: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str
