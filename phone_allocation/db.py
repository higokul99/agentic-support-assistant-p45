from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from phone_allocation.config import get_settings


class Base(DeclarativeBase):
    pass


class LdapPersonRow(Base):
    """Mirrors `public.ldap_people` (directory / LDAP sync)."""

    __tablename__ = "ldap_people"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    userid: Mapped[str] = mapped_column(String(255), nullable=False)
    fullname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emp_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    building: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PhoneNumberRow(Base):
    __tablename__ = "phone_numbers"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    location: Mapped[str] = mapped_column(String(128))
    building: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="available")


class AllocationRow(Base):
    __tablename__ = "allocations"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    userid: Mapped[str] = mapped_column(String(64), index=True)
    phone_number: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class LogRow(Base):
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String(128), index=True)
    data: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


_engine = None
_SessionLocal = None


def _engine_session():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        if settings.database_url.startswith("sqlite"):
            _engine = create_engine(
                settings.database_url,
                connect_args={"check_same_thread": False},
            )
        else:
            _engine = create_engine(settings.database_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine, _SessionLocal


def init_db() -> None:
    engine, _ = _engine_session()
    Base.metadata.create_all(bind=engine)


def insert_log(event: str, payload: Any) -> None:
    _, SessionLocal = _engine_session()
    with SessionLocal() as session:
        session.add(LogRow(event=event, data=json.dumps(payload, default=str)))
        session.commit()


def record_allocation(userid: str, phone_number: str, status: str = "active") -> None:
    _, SessionLocal = _engine_session()
    with SessionLocal() as session:
        session.add(
            AllocationRow(userid=userid, phone_number=phone_number, status=status)
        )
        session.commit()


def get_active_allocation(userid: str) -> str | None:
    """Returns the currently active phone number assigned to the user, if any."""
    _, SessionLocal = _engine_session()
    with SessionLocal() as session:
        return session.scalar(
            select(AllocationRow.phone_number).where(
                AllocationRow.userid == userid,
                AllocationRow.status == "active"
            )
        )


def list_available_numbers_for_site(location: str, building: str) -> list[str]:
    """Numbers in `phone_numbers` with status available for location + building."""
    _, SessionLocal = _engine_session()
    with SessionLocal() as session:
        rows = session.scalars(
            select(PhoneNumberRow.number).where(
                PhoneNumberRow.location == location,
                PhoneNumberRow.building == building,
                PhoneNumberRow.status == "available",
            )
        ).all()
    return list(rows)


def reserve_phone_number_in_inventory(number: str) -> dict[str, str]:
    """Mark a row in `phone_numbers` as reserved; returns status payload for the agent."""
    _, SessionLocal = _engine_session()
    with SessionLocal() as session:
        row = session.scalar(select(PhoneNumberRow).where(PhoneNumberRow.number == number))
        if not row:
            return {"status": "not_found", "number": number}
        if row.status != "available":
            return {"status": "not_available", "number": number, "current_status": row.status}
        row.status = "reserved"
        session.commit()
        return {"status": "reserved", "number": number}
