from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    Numeric, String, Text, Enum as SAEnum
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class ProjectStatus(str, enum.Enum):
    new = "new"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(50), nullable=True)
    telegram = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    clients = relationship("Client", back_populates="partner")
    projects = relationship("Project", back_populates="partner")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(50), nullable=True)
    monthly_fee = Column(Numeric(12, 2), default=0)
    dev_price = Column(Numeric(14, 2), default=0)
    advance_amount = Column(Numeric(14, 2), default=0)
    currency = Column(String(3), default="RUB")
    is_active = Column(Boolean, default=True)
    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    partner = relationship("Partner", back_populates="clients")
    payments = relationship("Payment", back_populates="client", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="client")
    documents = relationship("Document", back_populates="client")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    partner_id = Column(Integer, ForeignKey("partners.id"), nullable=True)
    status = Column(SAEnum(ProjectStatus), default=ProjectStatus.new, nullable=False)
    total_amount = Column(Numeric(14, 2), default=0)
    advance_amount = Column(Numeric(14, 2), default=0)
    my_share = Column(Numeric(14, 2), default=0)
    currency = Column(String(3), default="RUB")
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="projects")
    partner = relationship("Partner", back_populates="projects")
    payments = relationship("ProjectPayment", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="project")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="RUB")
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="payments")


class ProjectPayment(Base):
    __tablename__ = "project_payments"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    payment_type = Column(String(20), default="partial")  # advance / final / partial
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(3), default="RUB")
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="payments")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    doc_type = Column(String(20), default="other")  # contract / invoice / act / other
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(300), nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="documents")
    client = relationship("Client", back_populates="documents")
