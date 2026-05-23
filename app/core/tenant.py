import contextvars

# Global context variable to store the tenant ID for the current request
current_tenant_var: contextvars.ContextVar[str] = contextvars.ContextVar("tenant", default="default")

def set_tenant(tenant_id: str) -> contextvars.Token:
    """Set the current tenant and return the token to allow resetting later."""
    return current_tenant_var.set(tenant_id)

def get_tenant() -> str:
    """Get the current tenant ID."""
    return current_tenant_var.get()

def reset_tenant(token: contextvars.Token) -> None:
    """Reset the tenant context using the token."""
    current_tenant_var.reset(token)
