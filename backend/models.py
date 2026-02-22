from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    age = Column(Integer)
    hashed_password = Column(String)

    posts = relationship("Post", back_populates="author")
    messages = relationship("Message", back_populates="sender")

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    comment = Column(String)
    author_id = Column(Integer, ForeignKey("users.id"))

    author = relationship("User", back_populates="posts")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    content = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    is_read = Column(Boolean, default=False)

    sender = relationship("User", back_populates="messages")