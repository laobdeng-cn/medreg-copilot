import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from conftest import (
    test_document_repository,
    test_document_service,
    test_source_fetcher,
    test_task_dispatcher,
)
from fastapi.testclient import TestClient
from openpyxl import Workbook

from medreg.main import app
from medreg.modules.documents.fetcher import (
    ControlledOfficialSourceFetcher,
    FetchedSource,
)
from medreg.modules.documents.schemas import ParseStatus
from medreg.modules.documents.service import DocumentParseError

client = TestClient(app)


def source_payload() -> dict:
    return {
        "title": "医疗器械注册与备案管理办法",
        "issuing_authority": "国家市场监督管理总局",
        "jurisdiction": "CN",
        "regulation_type": "regulation",
        "scope_summary": "境内医疗器械注册与备案管理通用规章。",
        "initial_version": {
            "version_label": "2021版",
            "document_number": "国家市场监督管理总局令第47号",
            "official_url": "https://www.samr.gov.cn/example",
            "published_on": "2021-08-26",
            "effective_on": "2021-10-01",
            "expires_on": None,
        },
    }


async def create_version() -> str:
    source = client.post("/api/v1/regulation-sources", json=source_payload()).json()
    version_id = source["versions"][0]["id"]
    await test_document_repository.register_version(uuid.UUID(version_id))
    return version_id


@pytest.mark.asyncio
async def test_archive_parse_and_list_text_document() -> None:
    version_id = await create_version()

    archived_response = client.post(
        f"/api/v1/regulation-versions/{version_id}/documents",
        files={"file": ("regulation.txt", "第一章 总则\n本办法适用于境内注册。", "text/plain")},
        data={"uploaded_by": "刘凯旗"},
    )

    assert archived_response.status_code == 201
    archived = archived_response.json()
    assert archived["storage_status"] == "archived"
    assert archived["parse_status"] == "pending"
    assert archived["sha256"]
    assert archived["security_status"] == "passed"
    assert archived["security_engine"] == "controlled-intake-v1"
    assert archived["detected_type"] == "text"

    queued_response = client.post(f"/api/v1/documents/{archived['id']}/parse")

    assert queued_response.status_code == 202
    queued = queued_response.json()
    assert queued["parse_status"] == "queued"
    assert queued["parse_task_id"]
    assert test_task_dispatcher.parse_tasks == [
        (uuid.UUID(archived["id"]), queued["parse_task_id"])
    ]

    parsed = await test_document_service.execute_parse(
        uuid.UUID(archived["id"]), queued["parse_task_id"]
    )
    assert parsed.parse_status.value == "completed"
    assert parsed.parse_attempts == 1
    assert parsed.extracted_char_count > 10
    assert parsed.segmenter_version == "legal-hierarchy-v1"
    assert parsed.section_count == 1
    assert parsed.chunk_count == 1

    structure_response = client.get(
        f"/api/v1/documents/{archived['id']}/structure"
    )
    assert structure_response.status_code == 200
    structure = structure_response.json()
    assert structure["section_count"] == 1
    assert structure["chunk_count"] == 1
    assert structure["table_count"] == 0
    assert structure["sections"][0]["heading"] == "第一章 总则"
    assert structure["chunks"][0]["content"].startswith("第一章 总则")

    list_response = client.get(
        f"/api/v1/regulation-versions/{version_id}/documents"
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


@pytest.mark.asyncio
async def test_duplicate_document_is_rejected() -> None:
    version_id = await create_version()
    request = {
        "files": {"file": ("same.txt", "same content", "text/plain")},
        "data": {"uploaded_by": "刘凯旗"},
    }

    first = client.post(
        f"/api/v1/regulation-versions/{version_id}/documents", **request
    )
    duplicate = client.post(
        f"/api/v1/regulation-versions/{version_id}/documents", **request
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_failed_parse_can_be_retried_with_visible_attempt_count() -> None:
    version_id = await create_version()
    archived = client.post(
        f"/api/v1/regulation-versions/{version_id}/documents",
        files={"file": ("broken.pdf", b"%PDF-1.7\ninvalid body", "application/pdf")},
        data={"uploaded_by": "刘凯旗"},
    ).json()

    first = client.post(f"/api/v1/documents/{archived['id']}/parse")
    with pytest.raises(DocumentParseError):
        await test_document_service.execute_parse(
            uuid.UUID(archived["id"]), first.json()["parse_task_id"]
        )
    second = client.post(f"/api/v1/documents/{archived['id']}/parse")
    with pytest.raises(DocumentParseError):
        await test_document_service.execute_parse(
            uuid.UUID(archived["id"]), second.json()["parse_task_id"]
        )

    assert first.status_code == 202
    assert second.status_code == 202
    listed = client.get(
        f"/api/v1/regulation-versions/{version_id}/documents"
    ).json()["items"][0]
    assert listed["parse_status"] == "failed"
    assert listed["parse_attempts"] == 2
    assert listed["parse_error"]


@pytest.mark.asyncio
async def test_unsupported_document_type_is_rejected_before_storage() -> None:
    version_id = await create_version()

    response = client.post(
        f"/api/v1/regulation-versions/{version_id}/documents",
        files={"file": ("script.exe", b"invalid", "application/octet-stream")},
        data={"uploaded_by": "刘凯旗"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_spoofed_pdf_is_rejected_before_storage() -> None:
    version_id = await create_version()

    response = client.post(
        f"/api/v1/regulation-versions/{version_id}/documents",
        files={"file": ("spoofed.pdf", b"plain text", "application/pdf")},
        data={"uploaded_by": "刘凯旗"},
    )

    assert response.status_code == 422
    assert "file signature" in response.json()["detail"]
    assert await test_document_repository.list_for_version(uuid.UUID(version_id)) == []


@pytest.mark.asyncio
async def test_xlsx_tables_are_persisted_in_document_structure() -> None:
    version_id = await create_version()
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "申报资料矩阵"
    worksheet.append(["资料类别", "状态", "责任人"])
    worksheet.append(["风险分析", "已接受", "刘凯旗"])
    worksheet.append(["临床评价", "待补充", "张法规"])
    buffer = BytesIO()
    workbook.save(buffer)

    archived = client.post(
        f"/api/v1/regulation-versions/{version_id}/documents",
        files={
            "file": (
                "dossier-matrix.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"uploaded_by": "刘凯旗"},
    )
    queued = client.post(f"/api/v1/documents/{archived.json()['id']}/parse")
    parsed = await test_document_service.execute_parse(
        uuid.UUID(archived.json()["id"]), queued.json()["parse_task_id"]
    )
    structure = client.get(
        f"/api/v1/documents/{archived.json()['id']}/structure"
    ).json()

    assert archived.status_code == 201
    assert archived.json()["detected_type"] == "xlsx"
    assert parsed.table_count == 1
    assert structure["table_count"] == 1
    assert structure["tables"][0]["title"] == "申报资料矩阵"
    assert structure["tables"][0]["headers"] == ["资料类别", "状态", "责任人"]
    assert structure["tables"][0]["rows"][1] == ["临床评价", "待补充", "张法规"]


@pytest.mark.asyncio
async def test_approved_official_fetch_is_archived_and_queued_for_parse() -> None:
    version_id = await create_version()
    official_url = "https://www.samr.gov.cn/demo/rule.html"
    test_source_fetcher.add(
        official_url,
        FetchedSource(
            file_name="rule.html",
            content_type="text/html",
            data="<h1>注册资料要求</h1><p>申请人应提交产品技术要求。</p>".encode(),
            final_url=official_url,
        ),
    )

    created = client.post(
        f"/api/v1/regulation-versions/{version_id}/fetch-requests",
        json={
            "official_url": official_url,
            "requested_by": "刘凯旗",
            "reason": "归档监管机构公开原文",
        },
    )
    assert created.status_code == 201
    request = created.json()
    assert request["status"] == "pending_approval"

    reviewed = client.post(
        f"/api/v1/document-fetch-requests/{request['id']}/review",
        json={
            "decision": "approved",
            "reviewed_by": "法规负责人",
            "note": "来源属于允许的监管机构域名",
        },
    )
    assert reviewed.status_code == 200
    queued = reviewed.json()
    assert queued["status"] == "queued"
    assert test_task_dispatcher.fetch_tasks[-1] == (
        uuid.UUID(request["id"]),
        queued["task_id"],
    )

    completed = await test_document_service.execute_fetch(
        uuid.UUID(request["id"]), queued["task_id"]
    )
    assert completed.status.value == "completed"
    assert completed.resulting_document_id is not None
    assert test_task_dispatcher.parse_tasks

    parse_document_id, parse_task_id = test_task_dispatcher.parse_tasks[-1]
    parsed = await test_document_service.execute_parse(
        parse_document_id, parse_task_id
    )
    assert parsed.parse_status.value == "completed"
    assert parsed.extracted_char_count > 10


@pytest.mark.asyncio
async def test_fetch_request_can_be_rejected_with_audit_note() -> None:
    version_id = await create_version()
    created = client.post(
        f"/api/v1/regulation-versions/{version_id}/fetch-requests",
        json={
            "official_url": "https://www.nmpa.gov.cn/rules/demo.html",
            "requested_by": "刘凯旗",
            "reason": "请求归档",
        },
    ).json()

    response = client.post(
        f"/api/v1/document-fetch-requests/{created['id']}/review",
        json={
            "decision": "rejected",
            "reviewed_by": "法规负责人",
            "note": "链接不是目标法规原文",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["review_note"] == "链接不是目标法规原文"
    assert not test_task_dispatcher.fetch_tasks


@pytest.mark.asyncio
async def test_non_https_fetch_request_is_rejected_before_approval() -> None:
    version_id = await create_version()

    response = client.post(
        f"/api/v1/regulation-versions/{version_id}/fetch-requests",
        json={
            "official_url": "http://www.samr.gov.cn/rules/demo.html",
            "requested_by": "刘凯旗",
            "reason": "请求归档",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_stale_parse_is_requeued_with_a_new_task_id() -> None:
    version_id = await create_version()
    archived = client.post(
        f"/api/v1/regulation-versions/{version_id}/documents",
        files={"file": ("stale.txt", "等待恢复的解析任务", "text/plain")},
        data={"uploaded_by": "刘凯旗"},
    ).json()
    queued = client.post(f"/api/v1/documents/{archived['id']}/parse").json()
    document_id = uuid.UUID(archived["id"])
    stale_at = datetime.now(UTC) - timedelta(seconds=301)
    await test_document_repository.update_parse(
        document_id=document_id,
        status=ParseStatus.QUEUED,
        attempts=0,
        task_id=queued["parse_task_id"],
        parser_version=None,
        extracted_text=None,
        error=None,
        queued_at=stale_at,
        processing_started_at=None,
        parsed_at=None,
        updated_at=stale_at,
    )

    result = await test_document_service.recover_stale_parses()
    recovered = await test_document_repository.get(document_id)
    stale_result = await test_document_service.execute_parse(
        document_id, queued["parse_task_id"]
    )

    assert result.recovered == 1
    assert result.document_ids == [document_id]
    assert recovered is not None
    assert recovered.parse_task_id != queued["parse_task_id"]
    assert stale_result.parse_status == ParseStatus.QUEUED
    assert stale_result.parse_task_id == recovered.parse_task_id
    assert len(test_task_dispatcher.parse_tasks) == 2


def test_controlled_fetcher_only_accepts_approved_https_domains() -> None:
    fetcher = ControlledOfficialSourceFetcher(
        allowed_hosts=["samr.gov.cn", "nmpa.gov.cn"],
        timeout_seconds=1,
        max_bytes=1024,
    )

    fetcher.validate_url("https://www.nmpa.gov.cn/rules/demo.html")
    with pytest.raises(ValueError, match="allowlist"):
        fetcher.validate_url("https://example.com/rules/demo.html")
    with pytest.raises(ValueError, match="HTTPS"):
        fetcher.validate_url("http://www.samr.gov.cn/rules/demo.html")
