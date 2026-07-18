import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronRight,
  Library,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { regulationsApi } from "../api/client";
import { CreateRegulationDialog } from "../components/CreateRegulationDialog";
import { CreateRegulationVersionDialog } from "../components/CreateRegulationVersionDialog";
import { RegulationDetail } from "../components/RegulationDetail";
import { EvidenceRetrievalPanel } from "../components/EvidenceRetrievalPanel";
import type {
  RegulationSource,
  RegulationSourceCreate,
  RegulationType,
  RegulationVersionCreate,
} from "../types";

const typeLabels: Record<RegulationType, string> = {
  regulation: "部门规章",
  guidance: "指导原则",
  notice: "公告 / 通知",
  standard: "标准",
  technical_guideline: "技术指南",
};

function getLocalDateValue() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function RegulationsPage() {
  const [asOf, setAsOf] = useState(getLocalDateValue());
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [versionOpen, setVersionOpen] = useState(false);
  const [selected, setSelected] = useState<RegulationSource | null>(null);
  const queryClient = useQueryClient();

  const sources = useQuery({
    queryKey: ["regulation-sources", asOf],
    queryFn: () => regulationsApi.list(asOf),
  });

  const createSource = useMutation({
    mutationFn: regulationsApi.create,
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["regulation-sources"] });
      setCreateOpen(false);
      setSelected(created);
    },
  });

  const reviewVersion = useMutation({
    mutationFn: ({ sourceId, versionId }: { sourceId: string; versionId: string }) =>
      regulationsApi.reviewVersion(
        sourceId,
        versionId,
        {
          decision: "verified",
          reviewed_by: "刘凯旗",
          note: "已对照官方发布页面、发文字号及生效日期完成核验。",
        },
        asOf,
      ),
    onSuccess: async (reviewed) => {
      await queryClient.invalidateQueries({ queryKey: ["regulation-sources"] });
      setSelected(reviewed);
    },
  });

  const addVersion = useMutation({
    mutationFn: ({ sourceId, payload }: { sourceId: string; payload: RegulationVersionCreate }) =>
      regulationsApi.addVersion(sourceId, payload, asOf),
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ["regulation-sources"] });
      setVersionOpen(false);
      setSelected(updated);
    },
  });

  const allItems = sources.data?.items ?? [];
  const items = allItems.filter((source) => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return true;
    return [
      source.code,
      source.title,
      source.issuing_authority,
      source.scope_summary,
      ...source.versions.map((version) => version.document_number),
    ]
      .join(" ")
      .toLowerCase()
      .includes(keyword);
  });
  const versions = allItems.flatMap((source) => source.versions);
  const verifiedCount = versions.filter((version) => version.review_status === "verified").length;
  const pendingCount = versions.filter(
    (version) => version.review_status === "pending_review",
  ).length;
  const applicableCount = allItems.filter((source) => source.applicable_version).length;

  function submitSource(payload: RegulationSourceCreate) {
    createSource.mutate(payload);
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">受控法规知识底座</span>
          <h1>法规知识库</h1>
          <p>登记官方来源、核验版本，并按申报基准日期确定当时适用的法规。</p>
        </div>
        <button className="button primary" type="button" onClick={() => setCreateOpen(true)}>
          <Plus size={17} />
          登记官方来源
        </button>
      </div>

      <section className="metric-strip regulation-metrics" aria-label="法规知识库指标">
        <div>
          <span>法规来源</span>
          <strong>{allItems.length}</strong>
          <small>按法规主题归档</small>
        </div>
        <div>
          <span>已核验版本</span>
          <strong>{verifiedCount}</strong>
          <small>可参与适用性判断</small>
        </div>
        <div>
          <span>待人工核验</span>
          <strong>{pendingCount}</strong>
          <small>不可进入 RAG 证据</small>
        </div>
        <div>
          <span>当前适用来源</span>
          <strong>{applicableCount}</strong>
          <small>基准日期 {asOf}</small>
        </div>
      </section>

      <EvidenceRetrievalPanel />

      <section className="data-section regulation-list-section">
        <div className="list-toolbar regulation-toolbar">
          <div className="search-field">
            <Search size={17} aria-hidden="true" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="搜索法规来源"
              placeholder="搜索名称、发文字号或颁布机关"
            />
          </div>
          <label className="as-of-field">
            <span>适用基准日期</span>
            <input
              type="date"
              value={asOf}
              onInput={(event) => setAsOf(event.currentTarget.value)}
            />
          </label>
          <span className="result-count">{items.length} 个来源</span>
        </div>

        {sources.isLoading && <div className="state-message">正在读取法规来源…</div>}
        {sources.isError && (
          <div className="state-message error-state">
            <AlertTriangle size={19} />
            <div>
              <strong>法规服务连接失败</strong>
              <span>{sources.error.message}</span>
            </div>
            <button
              className="icon-button"
              type="button"
              title="重新加载"
              onClick={() => sources.refetch()}
            >
              <RefreshCw size={17} />
            </button>
          </div>
        )}
        {!sources.isLoading && !sources.isError && items.length === 0 && (
          <div className="empty-state large-empty">
            <Library size={26} aria-hidden="true" />
            <div>
              <strong>{search ? "没有匹配的法规来源" : "尚未登记法规来源"}</strong>
              <span>
                {search
                  ? "换一个关键词继续查找。"
                  : "从官方发布页面登记首个版本，核验后才会成为可信来源。"}
              </span>
            </div>
            {!search && (
              <button className="button secondary" type="button" onClick={() => setCreateOpen(true)}>
                登记来源
              </button>
            )}
          </div>
        )}
        {items.length > 0 && (
          <div className="table-scroll">
            <table className="regulation-table">
              <thead>
                <tr>
                  <th>法规来源</th>
                  <th>颁布机关</th>
                  <th>类型</th>
                  <th>当前适用版本</th>
                  <th>生效日期</th>
                  <th>核验状态</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {items.map((source) => {
                  const latest = source.versions[0];
                  return (
                    <tr key={source.id} onClick={() => setSelected(source)} tabIndex={0}>
                      <td>
                        <strong>{source.title}</strong>
                        <span className="table-secondary">{source.code}</span>
                      </td>
                      <td>{source.issuing_authority}</td>
                      <td>{typeLabels[source.regulation_type]}</td>
                      <td>{source.applicable_version?.version_label ?? "尚无适用版本"}</td>
                      <td>{source.applicable_version?.effective_on ?? latest?.effective_on ?? "-"}</td>
                      <td>
                        <span className={`review review-${latest?.review_status ?? "pending_review"}`}>
                          {latest?.review_status === "verified"
                            ? "已核验"
                            : latest?.review_status === "rejected"
                              ? "已驳回"
                              : "待核验"}
                        </span>
                      </td>
                      <td>
                        <button
                          className="icon-button subtle"
                          type="button"
                          title="查看版本时间线"
                          aria-label={`查看 ${source.title}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelected(source);
                          }}
                        >
                          <ChevronRight size={18} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {createOpen && (
        <CreateRegulationDialog
          isPending={createSource.isPending}
          error={createSource.error?.message ?? null}
          onClose={() => {
            setCreateOpen(false);
            createSource.reset();
          }}
          onSubmit={submitSource}
        />
      )}
      {selected && (
        <RegulationDetail
          source={selected}
          reviewPending={reviewVersion.isPending}
          reviewError={reviewVersion.error?.message ?? null}
          onClose={() => {
            setSelected(null);
            setVersionOpen(false);
            reviewVersion.reset();
            addVersion.reset();
          }}
          onAddVersion={() => setVersionOpen(true)}
          onVerify={(versionId) =>
            reviewVersion.mutate({ sourceId: selected.id, versionId })
          }
        />
      )}
      {selected && versionOpen && (
        <CreateRegulationVersionDialog
          sourceTitle={selected.title}
          isPending={addVersion.isPending}
          error={addVersion.error?.message ?? null}
          onClose={() => {
            setVersionOpen(false);
            addVersion.reset();
          }}
          onSubmit={(payload) => addVersion.mutate({ sourceId: selected.id, payload })}
        />
      )}
    </div>
  );
}
