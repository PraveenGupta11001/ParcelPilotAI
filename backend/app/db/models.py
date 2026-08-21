from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from .session import Base
import datetime

class Account(Base):
    __tablename__ = "accounts"
    
    account_id = Column(String, primary_key=True)
    account_name = Column(String, nullable=False)
    plan = Column(String, nullable=False)  # Enterprise, Growth, Standard
    status = Column(String, nullable=False)
    csm = Column(String, nullable=True)
    contract_file = Column(String, nullable=True)
    premium_support = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    
    orders = relationship("Order", back_populates="account")
    tickets = relationship("Ticket", back_populates="account")

class Order(Base):
    __tablename__ = "orders"
    
    order_id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("accounts.account_id"), nullable=False)
    carrier = Column(String, nullable=False)
    status = Column(String, nullable=False)  # BOOKED, PICKED_UP, DELIVERED
    booked_at = Column(DateTime(timezone=True), nullable=False)
    pickup_window_start = Column(DateTime(timezone=True), nullable=False)
    pickup_window_end = Column(DateTime(timezone=True), nullable=False)
    pickup_actual_at = Column(DateTime(timezone=True), nullable=True)
    shipment_fee_inr = Column(Float, nullable=False)
    carrier_fault = Column(Boolean, nullable=True)
    customer_fault = Column(Boolean, nullable=True)
    cancellation_requested_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    
    account = relationship("Account", back_populates="orders")

class Ticket(Base):
    __tablename__ = "tickets"
    
    ticket_id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("accounts.account_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    channel = Column(String, nullable=False)  # CHAT, EMAIL, etc.
    assigned_to = Column(String, nullable=True)
    last_customer_message_at = Column(DateTime(timezone=True), nullable=True)
    historical_resolution = Column(Text, nullable=True)
    
    account = relationship("Account", back_populates="tickets")
    escalations = relationship("Escalation", back_populates="ticket")

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(String, primary_key=True)
    role = Column(String, nullable=False)  # customer, internal_support, internal_lead
    account_id = Column(String, ForeignKey("accounts.account_id"), nullable=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

class Escalation(Base):
    __tablename__ = "escalations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String, ForeignKey("tickets.ticket_id"), nullable=False)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    reason = Column(Text, nullable=False)
    amount = Column(Float, nullable=True)  # credit amount if service credit proposed
    status = Column(String, default="PENDING")  # PENDING, APPROVED, REJECTED
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    
    ticket = relationship("Ticket", back_populates="escalations")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_name = Column(String, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=False)  # 1536 dim for OpenAI fallback default
    authority_level = Column(Integer, nullable=False)  # 1 (high/signed agreement) to 5 (historical ticket resolution)
    effective_date = Column(Date, nullable=False)
    status = Column(String, nullable=False)  # CURRENT, DEPRECATED
    scope = Column(String, nullable=False)  # general, or specific account_id: ACCT-001

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String, nullable=True)
    user_id = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    input = Column(Text, nullable=False)
    output = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

class PendingAction(Base):
    __tablename__ = "pending_actions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    action_type = Column(String, nullable=False)  # CANCEL_ORDER, ISSUE_CREDIT, ESCALATE_TICKET
    order_id = Column(String, ForeignKey("orders.order_id"), nullable=True)
    ticket_id = Column(String, ForeignKey("tickets.ticket_id"), nullable=True)
    amount = Column(Float, nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(String, default="PENDING")  # PENDING, APPROVED, REJECTED
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

