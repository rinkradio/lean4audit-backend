import uuid
import enum
from datetime import datetime, date

from sqlalchemy import (
    String,
    DateTime,
    Date,
    Enum,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.five_s_category import FiveSCategory


class ObservationType(str, enum.Enum):
    FIVE_S = "5S"
    GEMBA = "GEMBA"
    SAFETY = "SAFETY"


class ObservationSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ObservationStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Observation(Base):
    """
    A single observation recorded during a 5S audit.

    One Audit can contain multiple Observations.
    Photos are stored separately and reference this record.

    Location is now stored directly as text instead of requiring
    the consultant to select a predefined Location record.
    """

    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    observation_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        index=True,
        nullable=False,
    )

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id"),
        nullable=False,
        index=True,
    )

    observation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ObservationType.FIVE_S.value,
        index=True,
    )

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("five_s_categories.id"),
        nullable=True,
        index=True,
    )

    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )

    # ---------------------------------------------------------
    # LOCATION
    # ---------------------------------------------------------
    #
    # Location is now entered manually by the consultant.
    #
    # Example:
    #   "Assembly Line 2"
    #   "Machine No. 14"
    #   "Warehouse A - Rack 5"
    #
    # The old observations.location_id database column is
    # intentionally not removed yet. This keeps existing data
    # safe during the migration.
    #
    location: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    severity: Mapped[ObservationSeverity] = mapped_column(
        Enum(
            ObservationSeverity,
            name="observation_severity",
        ),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    corrective_action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    responsible_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    target_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[ObservationStatus] = mapped_column(
        Enum(
            ObservationStatus,
            name="observation_status",
        ),
        default=ObservationStatus.OPEN,
        nullable=False,
        index=True,
    )

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ---------------------------------------------------------
    # RELATIONSHIPS
    # ---------------------------------------------------------

    audit: Mapped["Audit"] = relationship(
        "Audit",
        foreign_keys=[audit_id],
    )

    category: Mapped["FiveSCategory"] = relationship(
        "FiveSCategory",
        foreign_keys=[category_id],
    )

    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
    )


# ---------------------------------------------------------
# INDEXES
# ---------------------------------------------------------

Index(
    "ix_observations_audit_severity",
    Observation.audit_id,
    Observation.severity,
)

Index(
    "ix_observations_audit_status",
    Observation.audit_id,
    Observation.status,
)