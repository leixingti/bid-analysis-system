"""数据库迁移脚本 v2.2 → v2.3
在应用启动时自动执行，为已有的 PostgreSQL 表添加新列和新表。
"""
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)


async def run_migration(conn: AsyncConnection):
    """执行 v2.3 数据库迁移"""

    migrations = [
        # === projects 表新增列 ===
        ("projects", "analysis_config", "ALTER TABLE projects ADD COLUMN analysis_config JSON DEFAULT '{}'"),
        ("projects", "created_by", "ALTER TABLE projects ADD COLUMN created_by VARCHAR"),

        # === documents 表新增列 ===
        ("documents", "parse_error", "ALTER TABLE documents ADD COLUMN parse_error TEXT"),

        # === analysis_results 表新增列 ===
        ("analysis_results", "history_id", "ALTER TABLE analysis_results ADD COLUMN history_id VARCHAR"),

        # === 新表: analysis_histories ===
        (None, None, """
            CREATE TABLE IF NOT EXISTS analysis_histories (
                id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL REFERENCES projects(id),
                version INTEGER DEFAULT 1,
                status VARCHAR(20) DEFAULT 'running',
                progress INTEGER DEFAULT 0,
                current_step VARCHAR(100) DEFAULT '',
                risk_score FLOAT DEFAULT 0.0,
                risk_level VARCHAR(20) DEFAULT 'low',
                total_alerts INTEGER DEFAULT 0,
                dimension_scores JSON DEFAULT '{}',
                config_snapshot JSON DEFAULT '{}',
                document_count INTEGER DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMP WITHOUT TIME ZONE,
                completed_at TIMESTAMP WITHOUT TIME ZONE,
                triggered_by VARCHAR
            )
        """),

        # === 新表: audit_logs ===
        (None, None, """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR,
                username VARCHAR(100),
                action VARCHAR(50) NOT NULL,
                resource_type VARCHAR(50),
                resource_id VARCHAR,
                details JSON DEFAULT '{}',
                ip_address VARCHAR(50),
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            )
        """),

        # === 索引 ===
        (None, None, "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)"),
        (None, None, "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)"),
        (None, None, "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)"),
        (None, None, "CREATE INDEX IF NOT EXISTS idx_history_project ON analysis_histories(project_id)"),
    ]

    for table, column, sql in migrations:
        try:
            # 如果是给已有表加列，先检查列是否存在
            if table and column:
                check = await conn.execute(text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :table AND column_name = :column"
                ), {"table": table, "column": column})
                if check.fetchone():
                    continue  # 列已存在，跳过

            await conn.execute(text(sql))
            desc = f"ADD {table}.{column}" if table and column else sql.strip()[:60]
            logger.info(f"✅ Migration: {desc}")
        except Exception as e:
            # 忽略 "already exists" 类错误
            err_msg = str(e).lower()
            if "already exists" in err_msg or "duplicate" in err_msg:
                continue
            logger.warning(f"⚠️ Migration warning: {e}")

    await conn.commit()
    logger.info("✅ v2.3 database migration completed")
