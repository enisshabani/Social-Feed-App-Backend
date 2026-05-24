"""
KaPak - Database Configuration
SQLAlchemy engine, session, and base model setup.
"""
from sqlalchemy import Column, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, with_loader_criteria
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.tenant import get_tenant

settings = get_settings()

# Create SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    poolclass=NullPool,
    echo=settings.DEBUG,      # Log SQL queries in debug mode
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class TenantMixin:
    """Mixin to easily add tenant_id to models."""
    tenant_id = Column(String, index=True, nullable=False, default=get_tenant)


@event.listens_for(Session, "do_orm_execute")
def _add_tenant_filter(execute_state):
    """
    Automatically injects a tenant filter into all queries
    for models that inherit from TenantMixin or have a tenant_id column.
    """
    if (
        execute_state.is_select
        and not execute_state.is_column_load
        and not execute_state.is_relationship_load
        and not execute_state.execution_options.get("skip_tenant_filter")
    ):
        tenant_id = get_tenant()
        # Check if the query is against models that have tenant_id
        # with_loader_criteria automatically applies the condition to the matching entities
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantMixin,
                lambda cls: cls.tenant_id == tenant_id,
                include_aliases=True
            )
        )

def get_db():
    """
    Dependency that provides a database session.
    Usage in routers:
        db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
