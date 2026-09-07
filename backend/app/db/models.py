"""SQLAlchemy ORM models matching the PostgreSQL schema in init.sql."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    page_count = Column(Integer)
    status = Column(String, nullable=False, default="processing")
    sha256 = Column(Text, unique=True, nullable=False)

    # Relationships
    facts = relationship("Fact", back_populates="document", cascade="all, delete-orphan")
    issues = relationship(
        "ExtractionIssue", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Document {self.filename} ({self.status})>"


class Fact(Base):
    __tablename__ = "facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number = Column(Integer, nullable=False)
    fact_type = Column(Text, nullable=False)
    entity = Column(Text)
    metric = Column(Text)
    value = Column(Text)
    normalized_value = Column(Numeric)
    unit = Column(Text)
    time_period = Column(Text)
    scope = Column(Text)
    evidence_quote = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.5)
    attributes = Column(JSONB, default=dict)
    embedding = Column(Vector(768))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="facts")

    def __repr__(self):
        return f"<Fact {self.entity}: {self.metric}={self.value} ({self.fact_type})>"


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fact_a_id = Column(
        UUID(as_uuid=True), ForeignKey("facts.id", ondelete="CASCADE"), nullable=False
    )
    fact_b_id = Column(
        UUID(as_uuid=True), ForeignKey("facts.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.5)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    fact_a = relationship("Fact", foreign_keys=[fact_a_id])
    fact_b = relationship("Fact", foreign_keys=[fact_b_id])

    def __repr__(self):
        return f"<Relationship {self.relationship_type}: {self.fact_a_id} <-> {self.fact_b_id}>"


class ExtractionIssue(Base):
    __tablename__ = "extraction_issues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number = Column(Integer)
    issue_type = Column(Text, nullable=False)
    raw_text_snippet = Column(Text)
    detail = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="issues")

    def __repr__(self):
        return f"<ExtractionIssue {self.issue_type} on page {self.page_number}>"
