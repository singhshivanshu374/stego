"""
SecureStego — SQLAlchemy Database Models

User: Stores credentials, RSA public key, and encrypted private key.
Operation: Audit log of every encode/decode operation.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.postgres import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Registered user with RSA keypair for Mode B operations.

    Security notes:
      - password_hash: bcrypt hash, never plaintext (Rule 5.1).
      - public_key_pem: Stored in plaintext — it's public by definition.
      - encrypted_private_key: Private key encrypted at rest with a server-side
        master key (Rule 5.5). Trade-off: the server holds the master key, so
        this is NOT zero-knowledge. The more secure alternative is client-side
        key management where the server never sees the private key at all.
        This design is chosen for simplicity in a demo/portfolio context.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    public_key_pem = Column(Text, nullable=False)
    encrypted_private_key = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    operations_as_sender = relationship(
        "Operation", back_populates="sender", foreign_keys="Operation.sender_id"
    )
    operations_as_recipient = relationship(
        "Operation", back_populates="recipient", foreign_keys="Operation.recipient_id"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class Operation(Base):
    """Audit record for every encode/decode operation.

    Stores metadata only — never stores plaintext message content (Rule 5.1).
    Mirrored to MongoDB for distributed audit trail (Phase 3).
    """
    __tablename__ = "operations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operation_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    operation_type = Column(SAEnum("encode", "decode", name="operation_type_enum"), nullable=False)
    mode = Column(SAEnum("password", "user_bound", name="mode_enum"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Only for Mode B
    image_filename = Column(String(500), nullable=True)
    storage_path = Column(String(1000), nullable=True)
    status = Column(String(50), default="completed", nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    sender = relationship("User", back_populates="operations_as_sender", foreign_keys=[sender_id])
    recipient = relationship("User", back_populates="operations_as_recipient", foreign_keys=[recipient_id])

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB audit mirror."""
        return {
            "id": self.id,
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "mode": self.mode,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "image_filename": self.image_filename,
            "storage_path": self.storage_path,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Operation id={self.id} type={self.operation_type} mode={self.mode}>"
