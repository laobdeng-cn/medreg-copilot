#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failed=0

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf 'OK      %s\n' "$label"
  else
    printf 'MISSING %s\n' "$label"
    failed=1
  fi
}

check "Python virtual environment" test -x "$ROOT_DIR/backend/.venv/bin/python"
check "FastAPI project import" "$ROOT_DIR/backend/.venv/bin/python" -c "import medreg.main"
check "SQLAlchemy / asyncpg / Alembic" "$ROOT_DIR/backend/.venv/bin/python" -c "import sqlalchemy, asyncpg, alembic"
check "Celery / Redis task runtime" "$ROOT_DIR/backend/.venv/bin/python" -c "import celery, redis"
check "MinIO / document parsers / PDF reports" "$ROOT_DIR/backend/.venv/bin/python" -c "import minio, pypdf, docx, openpyxl, multipart, reportlab"
check "Controlled file intake security" env PYTHONPATH="$ROOT_DIR/backend/src" "$ROOT_DIR/backend/.venv/bin/python" -c "from medreg.modules.documents.security import ControlledFileSecurityInspector; assert ControlledFileSecurityInspector.version == 'controlled-intake-v1'"
check "Qdrant / FastEmbed retrieval" "$ROOT_DIR/backend/.venv/bin/python" -c "import qdrant_client, fastembed, onnxruntime"
check "Neo4j knowledge graph driver" "$ROOT_DIR/backend/.venv/bin/python" -c "import neo4j"
check "LangGraph agent runtime" "$ROOT_DIR/backend/.venv/bin/python" -c "import langgraph"
check "M5 evaluation dataset" env PYTHONPATH="$ROOT_DIR/backend/src" "$ROOT_DIR/backend/.venv/bin/python" -c "from medreg.modules.evaluation.dataset import VersionedEvaluationDataset; assert len(VersionedEvaluationDataset().cases) == 60"
check "Tenant RBAC and audit module" env PYTHONPATH="$ROOT_DIR/backend/src" "$ROOT_DIR/backend/.venv/bin/python" -c "from medreg.modules.security.schemas import ROLE_PERMISSIONS, TenantRole; assert len(ROLE_PERMISSIONS[TenantRole.OWNER]) == 4"
check "Frontend dependency tree" test -d "$ROOT_DIR/frontend/node_modules"
check "Docker Compose configuration" docker compose -f "$ROOT_DIR/compose.yaml" config

exit "$failed"
