from sqlalchemy import Column, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class FileHash(Base):
    __tablename__ = 'ag_file_hashes'

    file_path = Column(String, primary_key=True)
    file_hash = Column(Text)
