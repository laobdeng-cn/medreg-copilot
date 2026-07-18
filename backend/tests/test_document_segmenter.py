import uuid

from medreg.modules.documents.segmenter import LegalDocumentSegmenter


def test_legal_hierarchy_builds_chapter_section_and_article_paths() -> None:
    text = """第一章　总　则
第一条
本办法适用于境内注册。
第二章 申报要求
第一节 产品资料
第一百零一条
申请人应当提交产品技术要求和检验报告。
"""

    result = LegalDocumentSegmenter(max_chunk_chars=200).segment(
        uuid.UUID("11111111-1111-1111-1111-111111111111"), text
    )

    assert [section.kind for section in result.sections] == [
        "chapter",
        "article",
        "chapter",
        "section",
        "article",
    ]
    assert result.sections[-1].heading == "第一百零一条"
    assert result.sections[-1].citation_path == (
        "第二章 申报要求 / 第一节 产品资料 / 第一百零一条"
    )
    assert result.sections[-1].parent_id == result.sections[-2].id
    assert len(result.chunks) == 2
    assert result.chunks[-1].citation_label.endswith("第一百零一条")


def test_long_article_chunks_preserve_offsets_and_overlap() -> None:
    body = "。".join(f"第{i}项要求包含完整证据和审评说明" for i in range(80))
    text = f"第三章 技术审评\n第二十条\n{body}。"
    result = LegalDocumentSegmenter(
        max_chunk_chars=240,
        overlap_chars=40,
    ).segment(uuid.uuid4(), text)

    chunks = result.chunks
    assert len(chunks) > 3
    assert all(text[item.char_start : item.char_end] == item.content for item in chunks)
    assert all(item.char_count <= 240 for item in chunks)
    assert chunks[1].char_start < chunks[0].char_end
    assert [item.ordinal for item in chunks] == list(range(len(chunks)))


def test_unstructured_text_becomes_a_single_body_section() -> None:
    text = "产品综述\n本产品用于体外检测。"

    result = LegalDocumentSegmenter(max_chunk_chars=200).segment(uuid.uuid4(), text)

    assert len(result.sections) == 1
    assert result.sections[0].kind == "body"
    assert result.sections[0].content == text
    assert len(result.chunks) == 1
