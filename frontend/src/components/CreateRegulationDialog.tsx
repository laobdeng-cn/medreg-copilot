import { useState, type FormEvent } from "react";
import { AlertCircle, X } from "lucide-react";
import type { RegulationSourceCreate, RegulationType } from "../types";

interface CreateRegulationDialogProps {
  isPending: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: RegulationSourceCreate) => void;
}

export function CreateRegulationDialog({
  isPending,
  error,
  onClose,
  onSubmit,
}: CreateRegulationDialogProps) {
  const [regulationType, setRegulationType] = useState<RegulationType>("regulation");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const expiresOn = String(formData.get("expires_on") ?? "");
    onSubmit({
      title: String(formData.get("title")),
      issuing_authority: String(formData.get("issuing_authority")),
      jurisdiction: "CN",
      regulation_type: regulationType,
      scope_summary: String(formData.get("scope_summary")),
      initial_version: {
        version_label: String(formData.get("version_label")),
        document_number: String(formData.get("document_number")),
        official_url: String(formData.get("official_url")),
        published_on: String(formData.get("published_on")),
        effective_on: String(formData.get("effective_on")),
        expires_on: expiresOn || null,
      },
    });
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="create-dialog regulation-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-regulation-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="dialog-header">
          <div>
            <span className="eyebrow">受控知识来源</span>
            <h2 id="create-regulation-title">登记官方法规来源</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            title="关闭"
            aria-label="关闭法规登记窗口"
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-section-label">来源信息</div>
          <div className="form-grid">
            <label className="field field-wide">
              <span>法规名称</span>
              <input name="title" minLength={2} maxLength={240} required autoFocus />
            </label>
            <label className="field">
              <span>颁布机关</span>
              <input name="issuing_authority" minLength={2} maxLength={160} required />
            </label>
            <label className="field">
              <span>文件类型</span>
              <select
                value={regulationType}
                onChange={(event) => setRegulationType(event.target.value as RegulationType)}
              >
                <option value="regulation">部门规章</option>
                <option value="guidance">指导原则</option>
                <option value="notice">公告 / 通知</option>
                <option value="standard">标准</option>
                <option value="technical_guideline">技术指南</option>
              </select>
            </label>
            <label className="field field-wide">
              <span>适用范围摘要</span>
              <textarea
                name="scope_summary"
                minLength={2}
                maxLength={1000}
                rows={3}
                placeholder="描述适用产品、业务环节或申报场景"
                required
              />
            </label>
          </div>

          <div className="form-section-label version-section-label">首个版本</div>
          <div className="form-grid">
            <label className="field">
              <span>版本标识</span>
              <input name="version_label" placeholder="例：2021版" required />
            </label>
            <label className="field">
              <span>发文字号</span>
              <input name="document_number" placeholder="例：总局令第47号" required />
            </label>
            <label className="field field-wide">
              <span>官方来源网址</span>
              <input
                name="official_url"
                type="url"
                placeholder="https://www.samr.gov.cn/..."
                required
              />
              <small>登记后仍需人工打开官方页面并完成核验。</small>
            </label>
            <label className="field">
              <span>发布日期</span>
              <input name="published_on" type="date" required />
            </label>
            <label className="field">
              <span>生效日期</span>
              <input name="effective_on" type="date" required />
            </label>
            <label className="field field-wide">
              <span>失效日期（可选）</span>
              <input name="expires_on" type="date" />
            </label>
          </div>

          {error && (
            <div className="form-error" role="alert">
              <AlertCircle size={17} aria-hidden="true" />
              {error}
            </div>
          )}

          <div className="dialog-actions">
            <button type="button" className="button secondary" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="button primary" disabled={isPending}>
              {isPending ? "正在登记…" : "登记并进入待核验"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
