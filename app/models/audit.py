import uuid
import enum
from datetime import datetime, date

from sqlalchemy import String, DateTime, Date, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"


class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    audit_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        index=True,
        nullable=False,
    )

    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("zones.id"),
        nullable=False,
        index=True,
    )

    auditor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    audit_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Historical snapshot of the Zone Leader name.
    # Zone Leader is not an employee/user relationship.
    zone_leader: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    hod: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    status: Mapped[AuditStatus] = mapped_column(
        Enum(AuditStatus, name="audit_status"),
        default=AuditStatus.IN_PROGRESS,
        nullable=False,
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    zone = relationship("Zone")
    auditor = relationship(
        "User",
        foreign_keys=[auditor_id],
    )
