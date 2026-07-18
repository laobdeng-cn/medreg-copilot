import { ChevronRight } from "lucide-react";
import type { RegistrationApplication } from "../types";

const statusLabels: Record<RegistrationApplication["status"], string> = {
  draft: "草稿",
  intake: "资料收集",
  precheck: "预审中",
  in_review: "人工复核",
  needs_action: "待整改",
  ready_for_submission: "可申报",
  archived: "已归档",
};

interface ApplicationTableProps {
  items: RegistrationApplication[];
  onSelect: (application: RegistrationApplication) => void;
  compact?: boolean;
}

export function ApplicationTable({
  items,
  onSelect,
  compact = false,
}: ApplicationTableProps) {
  return (
    <div className="table-scroll">
      <table className={compact ? "compact" : undefined}>
        <thead>
          <tr>
            <th>项目 / 产品</th>
            {!compact && <th>注册申请人</th>}
            <th>管理类别</th>
            <th>法规基准</th>
            <th>资料进度</th>
            <th>状态</th>
            {!compact && <th>负责人</th>}
            <th aria-label="操作" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} onClick={() => onSelect(item)} tabIndex={0}>
              <td>
                <strong>{item.name}</strong>
                <span className="table-secondary">
                  {item.code} · {item.product_name}
                </span>
              </td>
              {!compact && <td>{item.applicant_name}</td>}
              <td>{item.device_class} 类</td>
              <td>{item.regulation_effective_on}</td>
              <td>
                <div className="progress-cell">
                  <div className="progress-track" aria-hidden="true">
                    <span style={{ width: `${item.completion_rate}%` }} />
                  </div>
                  <span>{Math.round(item.completion_rate)}%</span>
                </div>
              </td>
              <td>
                <span className={`status status-${item.status}`}>
                  {statusLabels[item.status]}
                </span>
              </td>
              {!compact && <td>{item.owner_name}</td>}
              <td>
                <button
                  className="icon-button subtle"
                  type="button"
                  title="查看项目资料清单"
                  aria-label={`查看 ${item.name}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelect(item);
                  }}
                >
                  <ChevronRight size={18} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
