from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class ProjectStatus(str, enum.Enum):
    CREATED = "created"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), default="")
    role = Column(String(20), default="analyst", comment="admin/analyst/auditor")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, comment="招标项目名称")
    project_code = Column(String(100), comment="项目编号")
    description = Column(Text, comment="项目描述")
    status = Column(String(20), default=ProjectStatus.CREATED)
    risk_score = Column(Float, default=0.0, comment="综合风险评分 0-100")
    risk_level = Column(String(20), default=RiskLevel.LOW)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="project", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    company_name = Column(String(255), comment="投标单位名称")
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_type = Column(String(20), comment="pdf/docx/doc")
    file_size = Column(Integer, comment="文件大小(字节)")
    file_hash = Column(String(64), comment="文件MD5")

    meta_author = Column(String(255), comment="文档作者")
    meta_company = Column(String(255), comment="文档公司")
    meta_last_modified_by = Column(String(255), comment="最后修改人")
    meta_created_time = Column(DateTime, comment="文档创建时间")
    meta_modified_time = Column(DateTime, comment="文档修改时间")
    meta_producer = Column(String(255), comment="PDF Producer")
    meta_creator = Column(String(255), comment="Creator 软件")
    meta_software_version = Column(String(100), comment="软件版本号")
    meta_extra = Column(JSON, default=dict, comment="其他元数据")

    full_text = Column(Text, comment="全文内容")
    text_length = Column(Integer, default=0)
    page_count = Column(Integer, default=0)

    fonts_used = Column(JSON, default=list, comment="使用的字体列表")
    format_info = Column(JSON, default=dict, comment="格式信息(行距、页边距等)")

    parsed = Column(Integer, default=0, comment="0=未解析 1=已解析 2=解析失败")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="documents")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)

    analysis_type = Column(String(50), nullable=False)

    doc_id_a = Column(String, ForeignKey("documents.id"), nullable=True)
    doc_id_b = Column(String, ForeignKey("documents.id"), nullable=True)
    company_a = Column(String(255))
    company_b = Column(String(255))

    score = Column(Float, default=0.0, comment="检测得分 0-1")
    risk_level = Column(String(20), default=RiskLevel.LOW)
    summary = Column(Text, comment="检测结果摘要")
    details = Column(JSON, default=dict, comment="详细检测数据")

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="analysis_results")
