import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  CloudDownload,
  FileText,
  LoaderCircle,
  ListTree,
  RefreshCw,
  ScanText,
  ShieldCheck,
  Table2,
  Upload,
  X,
} from "lucide-react";
import { documentsApi } from "../api/client";
import { DocumentIndexControl } from "./DocumentIndexControl";
import type { DocumentFetchStatus, DocumentParseStatus } from "../types";

const parseLabels: Record<DocumentParseStatus, string> = {
  pending: "待解析",
  queued: "已排队",
  processing: "解析中",
  completed: "已解析",
  failed: "解析失败",
};

const fetchLabels: Record<DocumentFetchStatus, string> = {
  pending_approval: "待审批",
  queued: "已排队",
  fetching: "抓取中",
  completed: "已归档",
  failed: "抓取失败",
  rejected: "已驳回",
};

const activeParseStatuses = new Set<DocumentParseStatus>(["queued", "processing"]);
const activeFetchStatuses = new Set<DocumentFetchStatus>(["queued", "fetching"]);

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

interface RegulationDocumentPanelProps {
  versionId: string;
  officialUrl: string;
}

export function RegulationDocumentPanel({
  versionId,
  officialUrl,
}: RegulationDocumentPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const documents = useQuery({
    queryKey: ["regulation-documents", versionId],
    queryFn: () => documentsApi.list(versionId),
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => activeParseStatuses.has(item.parse_status))
        ? 1500
        : false,
  });
  const fetchRequests = useQuery({
    queryKey: ["document-fetch-requests", versionId],
    queryFn: () => documentsApi.listFetchRequests(versionId),
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => activeFetchStatuses.has(item.status))
        ? 1500
        : false,
  });
  const structure = useQuery({
    queryKey: ["document-structure", selectedDocumentId],
    queryFn: () => documentsApi.getStructure(selectedDocumentId ?? ""),
    enabled: Boolean(selectedDocumentId),
  });

  const refreshWorkflow = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["regulation-documents", versionId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["document-fetch-requests", versionId],
      }),
    ]);
  };

  const uploadDocument = useMutation({
    mutationFn: (file: File) => documentsApi.upload(versionId, file, "刘凯旗"),
    onSuccess: refreshWorkflow,
  });
  const parseDocument = useMutation({
    mutationFn: documentsApi.parse,
    onSettled: refreshWorkflow,
  });
  const createFetch = useMutation({
    mutationFn: () => documentsApi.createFetchRequest(versionId, officialUrl),
    onSuccess: refreshWorkflow,
  });
  const reviewFetch = useMutation({
    mutationFn: ({
      requestId,
      decision,
    }: {
      requestId: string;
      decision: "approved" | "rejected";
    }) => documentsApi.reviewFetchRequest(requestId, decision),
    onSettled: refreshWorkflow,
  });
  const retryFetch = useMutation({
    mutationFn: documentsApi.retryFetchRequest,
    onSettled: refreshWorkflow,
  });

  const items = documents.data?.items ?? [];
  const latestFetch = fetchRequests.data?.items[0];
  const activeSectionId =
    selectedSectionId ??
    structure.data?.chunks[0]?.section_id ??
    structure.data?.sections[0]?.id ??
    "";
  const activeSection = structure.data?.sections.find(
    (section) => section.id === activeSectionId,
  );
  const activeChunks =
    structure.data?.chunks.filter((chunk) => chunk.section_id === activeSectionId) ?? [];
  const fetchBusy = Boolean(
    latestFetch &&
      (latestFetch.status === "pending_approval" ||
        activeFetchStatuses.has(latestFetch.status)),
  );
  const workflowError =
    uploadDocument.error ??
    parseDocument.error ??
    createFetch.error ??
    reviewFetch.error ??
    retryFetch.error;

  return (
    <section className="document-archive" aria-label="法规原文归档">
      <div className="document-archive-head">
        <div>
          <strong>原文归档</strong>
          <span>{documents.isLoading ? "读取中" : `${items.length} 个文件`}</span>
        </div>
        <div className="document-head-actions">
          <button
            className="button secondary compact-button"
            type="button"
            disabled={createFetch.isPending || fetchBusy}
            onClick={() => createFetch.mutate()}
          >
            {createFetch.isPending ? (
              <LoaderCircle className="spin" size={14} />
            ) : (
              <CloudDownload size={14} />
            )}
            {createFetch.isPending ? "提交中" : "申请抓取"}
          </button>
          <input
            ref={inputRef}
            className="visually-hidden"
            type="file"
            accept=".pdf,.docx,.xlsx,.txt,.md,.html,.htm"
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              if (file) uploadDocument.mutate(file);
              event.currentTarget.value = "";
            }}
          />
          <button
            className="button secondary compact-button"
            type="button"
            disabled={uploadDocument.isPending}
            onClick={() => inputRef.current?.click()}
          >
            {uploadDocument.isPending ? (
              <LoaderCircle className="spin" size={14} />
            ) : (
              <Upload size={14} />
            )}
            {uploadDocument.isPending ? "归档中" : "上传原文"}
          </button>
        </div>
      </div>

      {latestFetch && (
        <div className="fetch-workflow">
          <div className="fetch-workflow-main">
            <CloudDownload size={15} />
            <div>
              <span>
                官方来源抓取
                <b className={`fetch-status fetch-${latestFetch.status}`}>
                  {fetchLabels[latestFetch.status]}
                </b>
              </span>
              <small>
                {latestFetch.requested_by} · 任务 {latestFetch.task_id?.slice(0, 8) ?? "待分配"}
              </small>
              {latestFetch.fetch_error && <em>{latestFetch.fetch_error}</em>}
            </div>
          </div>
          <div className="fetch-workflow-actions">
            {latestFetch.status === "pending_approval" && (
              <>
                <button
                  className="icon-button subtle"
                  type="button"
                  title="批准抓取"
                  aria-label="批准抓取官方原文"
                  disabled={reviewFetch.isPending}
                  onClick={() =>
                    reviewFetch.mutate({
                      requestId: latestFetch.id,
                      decision: "approved",
                    })
                  }
                >
                  <Check size={16} />
                </button>
                <button
                  className="icon-button subtle danger-icon"
                  type="button"
                  title="驳回申请"
                  aria-label="驳回抓取申请"
                  disabled={reviewFetch.isPending}
                  onClick={() =>
                    reviewFetch.mutate({
                      requestId: latestFetch.id,
                      decision: "rejected",
                    })
                  }
                >
                  <X size={16} />
                </button>
              </>
            )}
            {latestFetch.status === "failed" && (
              <button
                className="icon-button subtle"
                type="button"
                title="重试抓取"
                aria-label="重试抓取官方原文"
                disabled={retryFetch.isPending}
                onClick={() => retryFetch.mutate(latestFetch.id)}
              >
                {retryFetch.isPending ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <RefreshCw size={16} />
                )}
              </button>
            )}
          </div>
        </div>
      )}

      {(documents.isError || fetchRequests.isError) && (
        <div className="document-message error-inline">
          <AlertCircle size={14} />
          {documents.error?.message ?? fetchRequests.error?.message}
        </div>
      )}
      {workflowError && (
        <div className="document-message error-inline">
          <AlertCircle size={14} /> {workflowError.message}
        </div>
      )}
      {!documents.isLoading && !documents.isError && items.length === 0 && (
        <div className="document-empty">
          <FileText size={17} />
          <span>尚未归档法规原文</span>
        </div>
      )}

      {items.length > 0 && (
        <div className="document-list">
          {items.map((document) => {
            const submitting =
              parseDocument.isPending && parseDocument.variables === document.id;
            const parsing = submitting || activeParseStatuses.has(document.parse_status);
            return (
              <article className="document-row" key={document.id}>
                <div className="document-icon">
                  {document.parse_status === "completed" ? (
                    <CheckCircle2 size={16} />
                  ) : (
                    <FileText size={16} />
                  )}
                </div>
                <div className="document-main">
                  <div className="document-title-line">
                    <strong>{document.file_name}</strong>
                    <span className={`parse-status parse-${document.parse_status}`}>
                      {submitting ? "提交中" : parseLabels[document.parse_status]}
                    </span>
                  </div>
                  <span className="document-meta">
                    {formatBytes(document.size_bytes)} · SHA {document.sha256.slice(0, 12)} · {document.uploaded_by}
                  </span>
                  <span className={`document-security document-security-${document.security_status}`}>
                    <ShieldCheck size={12} />
                    {document.security_status === "passed"
                      ? `安全检查通过 · ${document.detected_type.toUpperCase()} · ${document.security_findings.length} 项`
                      : "历史归档 · 待重新执行安全检查"}
                  </span>
                  {document.parse_task_id && parsing && (
                    <span className="document-result">
                      任务 {document.parse_task_id.slice(0, 8)} · 第 {document.parse_attempts + (document.parse_status === "queued" ? 1 : 0)} 次执行
                    </span>
                  )}
                  {document.parse_status === "completed" && (
                    <>
                      <span className="document-result">
                        已抽取 {document.extracted_char_count.toLocaleString()} 字符 · {document.section_count} 个章节 · {document.chunk_count} 个 Chunk · {document.table_count} 张表格
                      </span>
                      <DocumentIndexControl documentId={document.id} />
                    </>
                  )}
                  {document.parse_error && (
                    <span className="document-error">{document.parse_error}</span>
                  )}
                </div>
                {document.parse_status === "completed" ? (
                  <button
                    className="icon-button subtle"
                    type="button"
                    title="查看结构化引用"
                    aria-label={`查看结构化引用 ${document.file_name}`}
                    onClick={() => {
                      setSelectedDocumentId((current) =>
                        current === document.id ? null : document.id,
                      );
                      setSelectedSectionId(null);
                    }}
                  >
                    <ListTree size={16} />
                  </button>
                ) : (document.parse_status === "pending" ||
                    document.parse_status === "failed") && (
                  <button
                    className="icon-button subtle"
                    type="button"
                    title={document.parse_status === "failed" ? "重试解析" : "开始解析"}
                    aria-label={`${document.parse_status === "failed" ? "重试解析" : "开始解析"} ${document.file_name}`}
                    disabled={submitting}
                    onClick={() => parseDocument.mutate(document.id)}
                  >
                    {submitting ? (
                      <LoaderCircle className="spin" size={16} />
                    ) : document.parse_status === "failed" ? (
                      <RefreshCw size={16} />
                    ) : (
                      <ScanText size={16} />
                    )}
                  </button>
                )}
              </article>
            );
          })}
          {selectedDocumentId && (
            <div className="structure-inspector">
              <div className="structure-inspector-head">
                <div>
                  <strong>结构化引用</strong>
                  <span>
                    {structure.data
                      ? `${structure.data.section_count} 个章节 · ${structure.data.chunk_count} 个 Chunk · ${structure.data.table_count} 张表格`
                      : "读取中"}
                  </span>
                </div>
                <button
                  className="icon-button subtle"
                  type="button"
                  title="关闭结构化引用"
                  aria-label="关闭结构化引用"
                  onClick={() => {
                    setSelectedDocumentId(null);
                    setSelectedSectionId(null);
                  }}
                >
                  <X size={16} />
                </button>
              </div>
              {structure.isLoading && (
                <div className="structure-loading">
                  <LoaderCircle className="spin" size={15} /> 正在读取
                </div>
              )}
              {structure.isError && (
                <div className="document-message error-inline">
                  <AlertCircle size={14} /> {structure.error.message}
                </div>
              )}
              {structure.data && structure.data.tables.length > 0 && (
                <div className="document-table-inspector">
                  <div className="document-table-inspector-title">
                    <Table2 size={15} />
                    <div>
                      <strong>结构化表格</strong>
                      <span>{structure.data.tables.length} 张 · 保留表头、单元格与来源定位</span>
                    </div>
                  </div>
                  {structure.data.tables.map((table) => (
                    <div className="document-table-block" key={table.id}>
                      <div className="document-table-meta">
                        <strong>{table.title}</strong>
                        <span>{table.row_count} 行 × {table.column_count} 列 · {table.source_locator}</span>
                        <code>SHA {table.content_hash.slice(0, 10)}</code>
                      </div>
                      <div className="document-table-scroll">
                        <table>
                          <thead>
                            <tr>
                              {table.headers.map((header, index) => (
                                <th key={`${table.id}-head-${index}`}>{header}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {table.rows.slice(0, 8).map((row, rowIndex) => (
                              <tr key={`${table.id}-row-${rowIndex}`}>
                                {row.map((cell, cellIndex) => (
                                  <td key={`${table.id}-${rowIndex}-${cellIndex}`}>{cell || "-"}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {structure.data && structure.data.sections.length > 0 && (
                <>
                  <label className="structure-select-label">
                    引用节点
                    <select
                      value={activeSectionId}
                      onChange={(event) => setSelectedSectionId(event.target.value)}
                    >
                      {structure.data.sections.map((section) => (
                        <option key={section.id} value={section.id}>
                          {section.citation_path}
                        </option>
                      ))}
                    </select>
                  </label>
                  {activeSection && (
                    <div className="structure-node-meta">
                      <span>{activeSection.kind}</span>
                      <span>
                        字符 {activeSection.char_start}–{activeSection.char_end}
                      </span>
                      <span>SHA {activeSection.content_hash.slice(0, 10)}</span>
                    </div>
                  )}
                  <div className="chunk-preview-list">
                    {activeChunks.length === 0 ? (
                      <span className="structure-empty">该层级节点无独立 Chunk</span>
                    ) : (
                      activeChunks.map((chunk) => (
                        <article className="chunk-preview" key={chunk.id}>
                          <div>
                            <strong>Chunk {chunk.section_chunk_index + 1}</strong>
                            <span>
                              {chunk.char_count} 字符 · 约 {chunk.token_estimate} tokens · [{chunk.char_start}, {chunk.char_end})
                            </span>
                          </div>
                          <p>{chunk.content}</p>
                        </article>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
