from datetime import date

import pytest
from sqlalchemy import delete

from medreg.core.database import async_session_factory
from medreg.modules.regulations.models import RegulationSourceModel
from medreg.modules.regulations.repository import SQLAlchemyRegulationRepository
from medreg.modules.regulations.schemas import (
    RegulationSourceCreate,
    RegulationType,
    RegulationVersionCreate,
    ReviewDecision,
    VersionReviewCreate,
)
from medreg.modules.regulations.service import RegulationService


@pytest.mark.integration
async def test_verified_regulation_survives_a_new_database_session() -> None:
    source_id = None
    try:
        async with async_session_factory() as write_session:
            service = RegulationService(SQLAlchemyRegulationRepository(write_session))
            created = await service.create(
                RegulationSourceCreate(
                    title="法规来源持久化集成测试",
                    issuing_authority="集成测试机关",
                    regulation_type=RegulationType.REGULATION,
                    scope_summary="验证法规来源与版本可跨数据库会话读取。",
                    initial_version=RegulationVersionCreate(
                        version_label="测试版",
                        document_number="TEST-REG-001",
                        official_url="https://example.gov.cn/regulation/1",
                        published_on=date(2021, 8, 31),
                        effective_on=date(2021, 10, 1),
                    ),
                )
            )
            source_id = created.id
            reviewed = await service.review_version(
                created.id,
                created.versions[0].id,
                VersionReviewCreate(
                    decision=ReviewDecision.VERIFIED,
                    reviewed_by="集成测试人员",
                    note="已对照测试来源核验。",
                ),
                date(2026, 7, 16),
            )
            assert reviewed.applicable_version is not None

        async with async_session_factory() as read_session:
            service = RegulationService(SQLAlchemyRegulationRepository(read_session))
            restored = await service.get(created.id, date(2026, 7, 16))

        assert restored.code == created.code
        assert restored.versions[0].review_status.value == "verified"
        assert restored.applicable_version is not None
        assert restored.applicable_version.document_number == "TEST-REG-001"
    finally:
        if source_id is not None:
            async with async_session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(RegulationSourceModel).where(
                        RegulationSourceModel.id == source_id
                    )
                )
                await cleanup_session.commit()
