from pydantic import BaseModel, Field
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
    id: str
    name: str
    project_code: Optional[str]
    description: Optional[str]
    status: str
    risk_score: float
    risk_level: str
    created_at: datetime
    updated_at: datetime
    document_count: int = 0

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    total: int
    items: List[ProjectResponse]


# ===== Document Schemas =====
class DocumentResponse(BaseModel):
    id: str
    project_id: str
    company_name: Optional[str]
    file_name: str
    file_type: Optional[str]
    file_size: Optional[int]
    file_hash: Optional[str]
    meta_author: Optional[str]
    meta_company: Optional[str]
    meta_last_modified_by: Optional[str]
    meta_created_time: Optional[datetime]
    meta_modified_time: Optional[datetime]
    meta_producer: Optional[str]
    meta_creator: Optional[str]
    text_length: int = 0
    page_count: int = 0
    fonts_used: List[str] = []
    parsed: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentMetadataCompare(BaseModel):
    """元数据比对结果"""
    field: str
    doc_a_value: Optional[str]
    doc_b_value: Optional[str]
    is_match: bool


# ===== Analysis Schemas =====
class AnalysisResultResponse(BaseModel):
    id: str
    project_id: str
    analysis_type: str
    doc_id_a: Optional[str]
    doc_id_b: Optional[str]
    company_a: Optional[str]
    company_b: Optional[str]
    score: float
    risk_level: str
    summary: Optional[str]
    details: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisOverview(BaseModel):
    """项目分析总览"""
    project_id: str
    project_name: str
    total_documents: int
    total_alerts: int
    risk_score: float
    risk_level: str
    analysis_summary: Dict[str, Any] = {}
    results: List[AnalysisResultResponse] = []


class SimilarityPair(BaseModel):
    """文本相似度对比结果"""
    doc_a_id: str
    doc_b_id: str
    company_a: str
    company_b: str
    similarity_score: float
    similar_segments: List[Dict[str, Any]] = []


class RiskAlert(BaseModel):
    """风险预警条目"""
    alert_type: str
    risk_level: str
    title: str
    description: str
    involved_companies: List[str] = []
    score: float
    details: Dict[str, Any] = {}
