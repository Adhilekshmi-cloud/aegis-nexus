from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.db import Base


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    document_type = Column(String, nullable=False)
    revision = Column(String)
    effective_date = Column(String)
    trust_level = Column(String, default="unknown")
    extraction_status = Column(String, default="pending")
    source_path = Column(String)
    raw_text = Column(Text)

    evidence = relationship("Evidence", back_populates="document")


class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String, nullable=False, unique=True)
    entity_type = Column(String, nullable=False)
    aliases = Column(Text)
    identifiers = Column(Text)
    confidence = Column(Float, default=1.0)

    facts = relationship("Fact", back_populates="subject_entity")


class Fact(Base):
    __tablename__ = "facts"
    id = Column(Integer, primary_key=True, index=True)
    subject_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    predicate = Column(String, nullable=False)
    value = Column(Text)
    unit = Column(String)
    valid_from = Column(String)
    valid_to = Column(String)
    revision_scope = Column(String)
    confidence = Column(Float, default=1.0)
    extraction_method = Column(String)
    verification_status = Column(String, default="verified")
    subject_entity = relationship("Entity", back_populates="facts")
    evidence = relationship("Evidence", back_populates="fact")


class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True, index=True)
    fact_id = Column(Integer, ForeignKey("facts.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer)
    section = Column(String)
    table_reference = Column(String)
    source_text = Column(Text)
    bounding_box = Column(String)

    fact = relationship("Fact", back_populates="evidence")
    document = relationship("Document", back_populates="evidence")


class AliasResolution(Base):
    __tablename__ = "alias_resolutions"
    id = Column(Integer, primary_key=True, index=True)
    original_identifier = Column(String, nullable=False)
    canonical_identifier = Column(String, nullable=False)
    resolution_method = Column(String)
    confidence = Column(Float, default=0.0)
    supporting_evidence = Column(Text)
    human_review_status = Column(String, default="pending")


class Conflict(Base):
    __tablename__ = "conflicts"
    id = Column(Integer, primary_key=True, index=True)
    fact_ids = Column(String, nullable=False)
    conflict_type = Column(String, nullable=False)
    resolution_status = Column(String, default="open")
    explanation = Column(Text)


class Relationship(Base):
    __tablename__ = "relationships"
    id = Column(Integer, primary_key=True, index=True)
    source_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    relationship_type = Column(String, nullable=False)
    target_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    evidence_id = Column(Integer, ForeignKey("evidence.id"))


class IngestionReport(Base):
    __tablename__ = "ingestion_reports"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False)
    method = Column(String)
    notes = Column(Text)
