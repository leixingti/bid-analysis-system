from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey, Boolean, Index
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
    # 分析参数（可配置阈值）
    analysis_config = Column(JSON, default=dict, comment="项目级分析参数")
    created_by = Column(String, nullable=True, comment="创建人ID")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="project", cascade="all, delete-orphan")
    analysis_histories = relationship("AnalysisHistory", back_populates="project", cascade="all, delete-orphan")


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
    parse_error = Column(Text, nullable=True, comment="解析失败原因")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="documents")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    history_id = Column(String, ForeignKey("analysis_histories.id"), nullable=True, comment="关联的分析批次")

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


class AnalysisHistory(Base):
    """分析历史记录 — 保留每次分析的快照"""
    __tablename__ = "analysis_histories"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    version = Column(Integer, default=1, comment="分析版本号")
    status = Column(String(20), default="running", comment="running/completed/failed")
    progress = Column(Integer, default=0, comment="进度 0-100")
    current_step = Column(String(100), default="", comment="当前步骤描述")

    risk_score = Column(Float, default=0.0)
    risk_level = Column(String(20), default="low")
    total_alerts = Column(Integer, default=0)
    dimension_scores = Column(JSON, default=dict)

    config_snapshot = Column(JSON, default=dict, comment="本次分析使用的参数")
    document_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    triggered_by = Column(String, nullable=True, comment="触发人ID")

    project = relationship("Project", back_populates="analysis_histories")


class AuditLog(Base):
    """操作审计日志"""
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, nullable=True)
    username = Column(String(100), nullable=True)
    action = Column(String(50), nullable=False, comment="login/upload/analyze/export/delete等")
    resource_type = Column(String(50), nullable=True, comment="project/document/report等")
    resource_id = Column(String, nullable=True)
    details = Column(JSON, default=dict, comment="操作详情")
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_created", "created_at"),
    )
