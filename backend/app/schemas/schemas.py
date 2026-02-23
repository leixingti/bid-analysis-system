from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ===== Project Schemas =====
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="招标项目名称")
    project_code: Optional[str] = Field(None, max_length=100, description="项目编号")
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    project_code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    project_code: Optional[str] = None
    description: Optional[str] = None
    status: str
    risk_score: float = 0.0
    risk_level: str = "low"
    analysis_config: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    document_count: int = 0


class ProjectListResponse(BaseModel):
    total: int
    items: List[ProjectResponse]


class BatchDeleteRequest(BaseModel):
    project_ids: List[str]


# ===== Document Schemas =====
class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    company_name: Optional[str] = None
    file_name: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    meta_author: Optional[str] = None
    meta_company: Optional[str] = None
    meta_last_modified_by: Optional[str] = None
    meta_created_time: Optional[datetime] = None
    meta_modified_time: Optional[datetime] = None
    meta_producer: Optional[str] = None
    meta_creator: Optional[str] = None
    text_length: int = 0
    page_count: int = 0
    fonts_used: List[str] = []
    parsed: int = 0
    parse_error: Optional[str] = None
    created_at: datetime


class DocumentPreview(BaseModel):
    """文档预览响应"""
    id: str
    file_name: str
    company_name: Optional[str] = None
    text_preview: str = ""
    text_length: int = 0
    metadata: Dict[str, Any] = {}


class DocumentMetadataCompare(BaseModel):
    field: str
    doc_a_value: Optional[str] = None
    doc_b_value: Optional[str] = None
    is_match: bool


# ===== Analysis Schemas =====
class AnalysisResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    analysis_type: str
    doc_id_a: Optional[str] = None
    doc_id_b: Optional[str] = None
    company_a: Optional[str] = None
    company_b: Optional[str] = None
    score: float
    risk_level: str
    summary: Optional[str] = None
    details: Dict[str, Any] = {}
    created_at: datetime


class AnalysisOverview(BaseModel):
    project_id: str
    project_name: str
    total_documents: int
    total_alerts: int
    risk_score: float = 0.0
    risk_level: str = "low"
    analysis_summary: Dict[str, Any] = {}
    results: List[AnalysisResultResponse] = []


class AnalysisConfig(BaseModel):
    """可配置的分析参数"""
    similarity_threshold: float = Field(0.20, ge=0.0, le=1.0, description="文本相似度阈值")
    timestamp_diff_minutes: int = Field(5, ge=1, le=60, description="时间戳聚集窗口(分钟)")
    sentence_similarity_threshold: float = Field(0.4, ge=0.1, le=1.0, description="句子级相似度阈值")
    enable_content_similarity: bool = True
    enable_metadata_match: bool = True
    enable_format_match: bool = True
    enable_timestamp_cluster: bool = True
    enable_entity_cross: bool = True
    enable_error_pattern: bool = True
    enable_price_analysis: bool = True


class AnalysisProgress(BaseModel):
    """分析进度响应"""
    history_id: str
    status: str
    progress: int
    current_step: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class AnalysisHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    version: int
    status: str
    progress: int = 0
    risk_score: float = 0.0
    risk_level: str = "low"
    total_alerts: int = 0
    dimension_scores: Dict[str, Any] = {}
    document_count: int = 0
    config_snapshot: Dict[str, Any] = {}
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    triggered_by: Optional[str] = None


class SimilarityPair(BaseModel):
    doc_a_id: str
    doc_b_id: str
    company_a: str
    company_b: str
    similarity_score: float
    similar_segments: List[Dict[str, Any]] = []


class RiskAlert(BaseModel):
    alert_type: str
    risk_level: str
    title: str
    description: str
    involved_companies: List[str] = []
    score: float
    details: Dict[str, Any] = {}


# ===== Audit Log Schemas =====
class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Dict[str, Any] = {}
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogResponse]
