import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, FilePlus2, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { applicationsApi } from "../api/client";
import { ApplicationDetail } from "../components/ApplicationDetail";
import { ApplicationTable } from "../components/ApplicationTable";
import type { RegistrationApplication } from "../types";

export function DashboardPage() {
  const [selected, setSelected] = useState<RegistrationApplication | null>(null);
  const applications = useQuery({
    queryKey: ["registration-applications"],
    queryFn: applicationsApi.list,
  });

  const items = applications.data?.items ?? [];
  const missingCount = items.reduce(
    (total, item) =>
      total + item.requirements.filter((requirement) => requirement.status === "missing").length,
    0,
  );
  const averageCompletion = items.length
    ? Math.round(
        items.reduce((total, item) => total + item.completion_rate, 0) / items.length,
      )
    : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">注册业务总览</span>
          <h1>注册申报工作台</h1>
          <p>集中管理申报项目、法规基准、资料完整性与人工复核状态。</p>
        </div>
        <Link className="button primary" to="/applications?create=1">
          <FilePlus2 size={17} />
          新建申报项目
        </Link>
      </div>

      <section className="metric-strip" aria-label="项目指标">
        <div>
          <span>在管申报项目</span>
          <strong>{items.length}</strong>
          <small>境内 II / III 类</small>
        </div>
        <div>
          <span>草稿项目</span>
          <strong>{items.filter((item) => item.status === "draft").length}</strong>
          <small>待补齐项目元数据</small>
        </div>
        <div>
          <span>缺失资料类别</span>
          <strong>{missingCount}</strong>
          <small>按法定七类资料统计</small>
        </div>
        <div>
          <span>平均资料进度</span>
          <strong>{averageCompletion}%</strong>
          <small>仅统计已接受证据</small>
        </div>
      </section>

      <section className="workflow-band">
        <div className="section-heading">
          <div>
            <span className="eyebrow">受控工作流</span>
            <h2>申报处理阶段</h2>
          </div>
          <span className="workflow-note">AI 不可替代人工批准</span>
        </div>
        <ol className="workflow-steps">
          {[
            ["01", "项目建档", "锁定辖区、类别与法规日期"],
            ["02", "资料收集", "归档原始文档与版本"],
            ["03", "规则预审", "完整性、格式与一致性检查"],
            ["04", "人工复核", "确认问题、证据与整改意见"],
            ["05", "编制导出", "引用可追溯的受控输出"],
          ].map(([index, title, description]) => (
            <li key={index}>
              <span>{index}</span>
              <strong>{title}</strong>
              <small>{description}</small>
            </li>
          ))}
        </ol>
      </section>

      <section className="data-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">近期活动</span>
            <h2>申报项目</h2>
          </div>
          <Link className="text-link" to="/applications">
            查看全部 <ArrowRight size={16} />
          </Link>
        </div>

        {applications.isLoading && <div className="state-message">正在读取项目…</div>}
        {applications.isError && (
          <div className="state-message error-state">
            <AlertTriangle size={19} />
            <div>
              <strong>暂时无法连接项目服务</strong>
              <span>{applications.error.message}</span>
            </div>
            <button
              className="icon-button"
              type="button"
              title="重新加载"
              onClick={() => applications.refetch()}
            >
              <RefreshCw size={17} />
            </button>
          </div>
        )}
        {!applications.isLoading && !applications.isError && items.length === 0 && (
          <div className="empty-state">
            <FilePlus2 size={25} aria-hidden="true" />
            <div>
              <strong>还没有申报项目</strong>
              <span>创建首个项目后，系统会生成七类法定资料清单。</span>
            </div>
            <Link className="button secondary" to="/applications?create=1">
              开始建档
            </Link>
          </div>
        )}
        {items.length > 0 && (
          <ApplicationTable items={items.slice(0, 5)} onSelect={setSelected} compact />
        )}
      </section>

      {selected && (
        <ApplicationDetail
          application={selected}
          onClose={() => setSelected(null)}
          onUpdated={(updated) => {
            setSelected(updated);
            void applications.refetch();
          }}
        />
      )}
    </div>
  );
}
