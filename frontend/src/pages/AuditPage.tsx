import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  CircleUserRound,
  Database,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  ScrollText,
  ShieldCheck,
  Users,
} from "lucide-react";
import { securityApi } from "../api/client";
import type {
  AuditEvent,
  SecurityPermission,
  TenantRole,
} from "../types";

const ROLE_LABELS: Record<TenantRole, string> = {
  owner: "租户负责人",
  reviewer: "法规复核人",
  editor: "项目编辑者",
  viewer: "只读观察员",
};

const PERMISSION_LABELS: Record<SecurityPermission, string> = {
  read: "查看",
  write: "编辑",
  review: "复核",
  admin: "管理",
};

const ROLE_PERMISSIONS: Record<TenantRole, SecurityPermission[]> = {
  owner: ["read", "write", "review", "admin"],
  reviewer: ["read", "write", "review"],
  editor: ["read", "write"],
  viewer: ["read"],
};

const ACTION_LABELS: Record<string, string> = {
  "application.created": "创建申报项目",
  "evidence.archived": "归档申报证据",
  "requirement.reviewed": "复核资料要求",
  "precheck.completed": "完成资料预审",
  "precheck_report.exported": "导出预审报告",
  "finding.remediation_updated": "更新问题整改",
  "agent_run.created": "生成 Agent 草稿",
  "agent_run.reviewed": "复核 Agent 草稿",
  "evaluation.completed": "完成工程评测",
};

const ACTION_FILTERS = [
  { value: "all", label: "全部事件" },
  { value: "application.created", label: "申报" },
  { value: "evidence.archived", label: "证据" },
  { value: "precheck.completed", label: "预审" },
  { value: "agent_run.created", label: "Agent" },
  { value: "evaluation.completed", label: "评测" },
] as const;

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function shortResource(event: AuditEvent) {
  if (!event.resource_id) return "-";
  return event.resource_id.length > 20
    ? `${event.resource_id.slice(0, 8)}…${event.resource_id.slice(-4)}`
    : event.resource_id;
}

export function AuditPage() {
  const [actionFilter, setActionFilter] = useState("all");
  const workspace = useQuery({
    queryKey: ["security-workspace"],
    queryFn: securityApi.workspace,
  });
  const events = useQuery({
    queryKey: ["audit-events", actionFilter],
    queryFn: () =>
      securityApi.auditEvents(actionFilter === "all" ? undefined : actionFilter),
  });

  const actor = workspace.data?.current_actor;

  return (
    <div className="page audit-page">
      <div className="page-header audit-page-header">
        <div>
          <span className="eyebrow">Tenant Security</span>
          <h1>权限与审计</h1>
          <p>核对租户身份、成员角色、关键操作和受控资源访问轨迹。</p>
        </div>
        <div className="audit-actor-badge">
          <CircleUserRound size={18} />
          <span>
            <small>当前身份</small>
            <strong>{actor ? `${actor.user_name} · ${ROLE_LABELS[actor.role]}` : "读取中"}</strong>
          </span>
        </div>
      </div>

      <section className="audit-summary-band" aria-label="租户权限摘要">
        <div>
          <Database size={17} />
          <span>租户空间</span>
          <strong>{workspace.data?.tenant_name ?? "读取中"}</strong>
        </div>
        <div>
          <KeyRound size={17} />
          <span>当前角色</span>
          <strong>{actor ? ROLE_LABELS[actor.role] : "-"}</strong>
        </div>
        <div>
          <Users size={17} />
          <span>有效成员</span>
          <strong>{workspace.data?.members.length ?? 0} 人</strong>
        </div>
        <div>
          <ScrollText size={17} />
          <span>审计事件</span>
          <strong>{workspace.data?.audit_event_count ?? 0} 条</strong>
        </div>
      </section>

      {workspace.data && (
        <div className="audit-boundary-note">
          <LockKeyhole size={17} />
          <span>{workspace.data.boundary_note}</span>
        </div>
      )}

      <div className="audit-main-grid">
        <section className="audit-members-section">
          <div className="section-heading compact-heading">
            <div>
              <span className="eyebrow">RBAC</span>
              <h2>成员与权限矩阵</h2>
            </div>
            <span>{workspace.data?.members.length ?? 0} 个成员</span>
          </div>
          <div className="audit-member-table">
            <div className="audit-member-head">
              <span>成员</span>
              <span>角色</span>
              <span>权限</span>
              <span>状态</span>
            </div>
            {(workspace.data?.members ?? []).map((member) => (
              <div className="audit-member-row" key={member.user_id}>
                <div>
                  <strong>{member.display_name}</strong>
                  <span>{member.email}</span>
                </div>
                <strong>{ROLE_LABELS[member.role]}</strong>
                <div className="audit-permission-list">
                  {ROLE_PERMISSIONS[member.role].map((permission) => (
                    <span key={permission}>{PERMISSION_LABELS[permission]}</span>
                  ))}
                </div>
                <span className="audit-active-state">
                  <CheckCircle2 size={14} /> 有效
                </span>
              </div>
            ))}
          </div>
        </section>

        <aside className="audit-policy-panel">
          <div className="section-heading compact-heading">
            <div>
              <span className="eyebrow">Access Boundary</span>
              <h2>数据边界</h2>
            </div>
          </div>
          <div className="audit-policy-list">
            <div>
              <Fingerprint size={17} />
              <span>
                <strong>身份来源</strong>
                <small>租户成员关系与服务端角色解析</small>
              </span>
            </div>
            <div>
              <ShieldCheck size={17} />
              <span>
                <strong>租户隔离</strong>
                <small>申报与 Agent SQL 查询强制 tenant_id</small>
              </span>
            </div>
            <div>
              <ScrollText size={17} />
              <span>
                <strong>审计留痕</strong>
                <small>操作者、动作、资源、请求和结果不可变记录</small>
              </span>
            </div>
          </div>
        </aside>
      </div>

      <section className="audit-events-section">
        <div className="section-heading compact-heading audit-events-heading">
          <div>
            <span className="eyebrow">Immutable Event Feed</span>
            <h2>操作审计</h2>
          </div>
          <span>{events.data?.total ?? 0} 条记录</span>
        </div>
        <div className="audit-action-filters" aria-label="审计事件筛选">
          {ACTION_FILTERS.map((filter) => (
            <button
              type="button"
              key={filter.value}
              className={actionFilter === filter.value ? "active" : undefined}
              aria-pressed={actionFilter === filter.value}
              onClick={() => setActionFilter(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <div className="audit-event-table">
          <div className="audit-event-head">
            <span>时间 / 操作者</span>
            <span>动作</span>
            <span>资源</span>
            <span>请求</span>
            <span>结果</span>
          </div>
          {(events.data?.items ?? []).map((event) => (
            <article className="audit-event-row" key={event.id}>
              <div>
                <strong>{formatDateTime(event.created_at)}</strong>
                <span>{event.actor_name} · {ROLE_LABELS[event.actor_role]}</span>
              </div>
              <div>
                <strong>{ACTION_LABELS[event.action] ?? event.action}</strong>
                <span>{event.action}</span>
              </div>
              <div>
                <strong>{event.resource_type}</strong>
                <code title={event.resource_id ?? undefined}>{shortResource(event)}</code>
              </div>
              <div>
                <strong>{event.request_method}</strong>
                <span>{event.request_path}</span>
              </div>
              <span className="audit-success-state">
                <CheckCircle2 size={14} /> {event.status_code}
              </span>
            </article>
          ))}
          {!events.isLoading && !events.data?.items.length && (
            <div className="audit-empty-state">当前筛选下没有审计事件。</div>
          )}
        </div>
      </section>
    </div>
  );
}
