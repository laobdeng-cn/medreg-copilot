import { useState, type FormEvent } from "react";
import { AlertCircle, X } from "lucide-react";
import type {
  DeviceClass,
  RegistrationApplicationCreate,
} from "../types";

interface CreateApplicationDialogProps {
  isPending: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: RegistrationApplicationCreate) => void;
}

function getLocalDateValue() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const initialDate = getLocalDateValue();

export function CreateApplicationDialog({
  isPending,
  error,
  onClose,
  onSubmit,
}: CreateApplicationDialogProps) {
  const [deviceClass, setDeviceClass] = useState<DeviceClass>("II");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    onSubmit({
      name: String(formData.get("name")),
      product_name: String(formData.get("product_name")),
      applicant_name: String(formData.get("applicant_name")),
      jurisdiction: "CN_NMPA",
      device_class: deviceClass,
      application_type: "initial_registration",
      regulation_effective_on: String(formData.get("regulation_effective_on")),
      owner_name: String(formData.get("owner_name")),
    });
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="create-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="dialog-header">
          <div>
            <span className="eyebrow">NMPA 初次注册</span>
            <h2 id="create-title">新建申报项目</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            title="关闭"
            aria-label="关闭新建项目窗口"
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <label className="field field-wide">
              <span>项目名称</span>
              <input
                name="name"
                minLength={2}
                maxLength={120}
                placeholder="例：便携式心电记录仪注册申报"
                required
                autoFocus
              />
            </label>

            <label className="field">
              <span>产品名称</span>
              <input
                name="product_name"
                minLength={2}
                maxLength={160}
                placeholder="医疗器械产品名称"
                required
              />
            </label>

            <label className="field">
              <span>注册申请人</span>
              <input
                name="applicant_name"
                minLength={2}
                maxLength={160}
                placeholder="企业全称"
                required
              />
            </label>

            <fieldset className="field">
              <legend>管理类别</legend>
              <div className="segmented" aria-label="选择管理类别">
                {(["II", "III"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={deviceClass === value ? "selected" : undefined}
                    aria-pressed={deviceClass === value}
                    onClick={() => setDeviceClass(value)}
                  >
                    {value} 类
                  </button>
                ))}
              </div>
            </fieldset>

            <label className="field">
              <span>法规基准日期</span>
              <input
                type="date"
                name="regulation_effective_on"
                defaultValue={initialDate}
                required
              />
              <small>用于锁定该日期有效的法规版本。</small>
            </label>

            <label className="field field-wide">
              <span>项目负责人</span>
              <input
                name="owner_name"
                minLength={2}
                maxLength={80}
                defaultValue="刘凯旗"
                required
              />
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
              {isPending ? "正在创建…" : "创建项目"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
