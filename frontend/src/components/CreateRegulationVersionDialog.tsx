import { useState, type FormEvent } from "react";
import { AlertCircle, X } from "lucide-react";
import type { RegulationVersionCreate } from "../types";

interface CreateRegulationVersionDialogProps {
  sourceTitle: string;
  isPending: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: RegulationVersionCreate) => void;
}

export function CreateRegulationVersionDialog({
  sourceTitle,
  isPending,
  error,
  onClose,
  onSubmit,
}: CreateRegulationVersionDialogProps) {
  const [publishedOn, setPublishedOn] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const expiresOn = String(formData.get("expires_on") ?? "");
    onSubmit({
      version_label: String(formData.get("version_label")),
      document_number: String(formData.get("document_number")),
      official_url: String(formData.get("official_url")),
      published_on: publishedOn,
      effective_on: String(formData.get("effective_on")),
      expires_on: expiresOn || null,
    });
  }

  return (
    <div className="modal-backdrop version-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="create-dialog version-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-version-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="dialog-header">
          <div>
            <span className="eyebrow">{sourceTitle}</span>
            <h2 id="create-version-title">追加法规版本</h2>
          </div>
          <button className="icon-button" type="button" title="关闭" aria-label="关闭版本登记窗口" onClick={onClose}>
            <X size={19} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <label className="field">
              <span>版本标识</span>
              <input name="version_label" placeholder="例：2026修订版" required autoFocus />
            </label>
            <label className="field">
              <span>发文字号</span>
              <input name="document_number" required />
            </label>
            <label className="field field-wide">
              <span>官方来源网址</span>
              <input name="official_url" type="url" required />
              <small>新增版本默认为待核验，不会直接成为申报依据。</small>
            </label>
            <label className="field">
              <span>发布日期</span>
              <input
                name="published_on"
                type="date"
                value={publishedOn}
                onChange={(event) => setPublishedOn(event.target.value)}
                required
              />
            </label>
            <label className="field">
              <span>生效日期</span>
              <input name="effective_on" type="date" min={publishedOn || undefined} required />
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
            <button type="button" className="button secondary" onClick={onClose}>取消</button>
            <button type="submit" className="button primary" disabled={isPending}>
              {isPending ? "正在登记…" : "登记为待核验版本"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
