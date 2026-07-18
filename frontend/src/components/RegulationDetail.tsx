import { ExternalLink, FileCheck2, Plus, ShieldCheck, X } from "lucide-react";
import type { RegulationSource, RegulationVersion } from "../types";
import { RegulationDocumentPanel } from "./RegulationDocumentPanel";
import { RegulationGraphPanel } from "./RegulationGraphPanel";

const reviewLabels: Record<RegulationVersion["review_status"], string> = {
  pending_review: "待核验",
  verified: "已核验",
  rejected: "已驳回",
};

const lifecycleLabels: Record<RegulationVersion["lifecycle_status"], string> = {
  unknown: "未知",
  upcoming: "未生效",
  effective: "有效",
  expired: "已失效",
};

interface RegulationDetailProps {
  source: RegulationSource;
  reviewPending: boolean;
  reviewError: string | null;
  onClose: () => void;
  onAddVersion: () => void;
  onVerify: (versionId: string) => void;
}

export function RegulationDetail({
  source,
  reviewPending,
  reviewError,
  onClose,
  onAddVersion,
  onVerify,
}: RegulationDetailProps) {
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside
        className="detail-drawer regulation-detail"
        role="dialog"
        aria-modal="true"
        aria-labelledby="regulation-detail-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="drawer-header">
          <div>
            <span className="eyebrow">{source.code}</span>
            <h2 id="regulation-detail-title">{source.title}</h2>
            <p>{source.issuing_authority}</p>
          </div>
          <button
            className="icon-button"
            type="button"
            title="关闭"
            aria-label="关闭法规详情"
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </div>

        <dl className="detail-facts regulation-facts">
          <div>
            <dt>管辖区域</dt>
            <dd>中国（CN）</dd>
          </div>
          <div>
            <dt>版本数量</dt>
            <dd>{source.versions.length} 个</dd>
          </div>
          <div className="fact-wide">
            <dt>适用范围</dt>
            <dd>{source.scope_summary}</dd>
          </div>
        </dl>

        <section className="applicable-version-band">
          <FileCheck2 size={19} aria-hidden="true" />
          <div>
            <span>当前基准日期适用版本</span>
            <strong>
              {source.applicable_version
                ? `${source.applicable_version.version_label} · ${source.applicable_version.document_number}`
                : "暂无已核验的适用版本"}
            </strong>
          </div>
        </section>

        <RegulationGraphPanel sourceId={source.id} />

        <section className="requirements-section regulation-versions-section">
          <div className="section-heading compact-heading">
            <div>
              <span className="eyebrow">版本控制</span>
              <h3>版本时间线</h3>
            </div>
            <div className="section-heading-actions">
              <span className="requirement-count">{source.versions.length} 个版本</span>
              <button className="button secondary compact-button" type="button" onClick={onAddVersion}>
                <Plus size={14} />
                追加版本
              </button>
            </div>
          </div>

          <div className="version-timeline">
            {source.versions.map((version) => (
              <article key={version.id} className="version-entry">
                <div className="version-entry-head">
                  <div>
                    <strong>{version.version_label}</strong>
                    <span>{version.document_number}</span>
                  </div>
                  <div className="version-statuses">
                    <span className={`lifecycle lifecycle-${version.lifecycle_status}`}>
                      {lifecycleLabels[version.lifecycle_status]}
                    </span>
                    <span className={`review review-${version.review_status}`}>
                      {reviewLabels[version.review_status]}
                    </span>
                  </div>
                </div>
                <dl className="version-dates">
                  <div>
                    <dt>发布</dt>
                    <dd>{version.published_on}</dd>
                  </div>
                  <div>
                    <dt>生效</dt>
                    <dd>{version.effective_on}</dd>
                  </div>
                  <div>
                    <dt>失效</dt>
                    <dd>{version.expires_on ?? "未设置"}</dd>
                  </div>
                </dl>
                <div className="version-actions">
                  <a
                    className="text-link"
                    href={version.official_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开官方来源 <ExternalLink size={14} />
                  </a>
                  {version.review_status === "pending_review" && (
                    <button
                      type="button"
                      className="button verify-button"
                      disabled={reviewPending}
                      onClick={() => onVerify(version.id)}
                    >
                      <ShieldCheck size={15} />
                      {reviewPending ? "正在核验…" : "核验通过"}
                    </button>
                  )}
                </div>
                {version.reviewed_by && (
                  <p className="review-record">
                    {version.reviewed_by} · {version.review_note}
                  </p>
                )}
                <RegulationDocumentPanel
                  versionId={version.id}
                  officialUrl={version.official_url}
                />
              </article>
            ))}
          </div>

          {reviewError && <div className="form-error">{reviewError}</div>}
        </section>
      </aside>
    </div>
  );
}
