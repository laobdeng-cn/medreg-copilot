import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FilePlus2, RefreshCw, Search } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { applicationsApi } from "../api/client";
import { ApplicationDetail } from "../components/ApplicationDetail";
import { ApplicationTable } from "../components/ApplicationTable";
import { CreateApplicationDialog } from "../components/CreateApplicationDialog";
import type {
  RegistrationApplication,
  RegistrationApplicationCreate,
} from "../types";

export function ApplicationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<RegistrationApplication | null>(null);
  const [createOpen, setCreateOpen] = useState(searchParams.get("create") === "1");
  const queryClient = useQueryClient();

  useEffect(() => {
    if (searchParams.get("create") === "1") {
      setCreateOpen(true);
    }
  }, [searchParams]);

  const applications = useQuery({
    queryKey: ["registration-applications"],
    queryFn: applicationsApi.list,
  });

  const createApplication = useMutation({
    mutationFn: applicationsApi.create,
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["registration-applications"] });
      setCreateOpen(false);
      setSearchParams({});
      setSelected(created);
    },
  });

  const items = (applications.data?.items ?? []).filter((item) => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return true;
    return [item.name, item.code, item.product_name, item.applicant_name, item.owner_name]
      .join(" ")
      .toLowerCase()
      .includes(keyword);
  });

  function closeCreateDialog() {
    setCreateOpen(false);
    setSearchParams({});
    createApplication.reset();
  }

  function submitApplication(payload: RegistrationApplicationCreate) {
    createApplication.mutate(payload);
  }

  async function updateSelected(application: RegistrationApplication) {
    setSelected(application);
    await queryClient.invalidateQueries({
      queryKey: ["registration-applications"],
    });
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">项目建档与资料基线</span>
          <h1>申报项目</h1>
          <p>为每个产品锁定注册路径、法规版本和法定资料清单。</p>
        </div>
        <button className="button primary" type="button" onClick={() => setCreateOpen(true)}>
          <FilePlus2 size={17} />
          新建申报项目
        </button>
      </div>

      <section className="data-section applications-section">
        <div className="list-toolbar">
          <div className="search-field">
            <Search size={17} aria-hidden="true" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="搜索申报项目"
              placeholder="搜索项目、产品、申请人或负责人"
            />
          </div>
          <span className="result-count">{items.length} 个项目</span>
        </div>

        {applications.isLoading && <div className="state-message">正在读取项目…</div>}
        {applications.isError && (
          <div className="state-message error-state">
            <AlertTriangle size={19} />
            <div>
              <strong>项目服务连接失败</strong>
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
          <div className="empty-state large-empty">
            <FilePlus2 size={26} aria-hidden="true" />
            <div>
              <strong>{search ? "没有匹配的项目" : "还没有申报项目"}</strong>
              <span>
                {search
                  ? "换一个关键词继续查找。"
                  : "新建项目后会立即生成七类法定资料清单。"}
              </span>
            </div>
            {!search && (
              <button className="button secondary" type="button" onClick={() => setCreateOpen(true)}>
                新建项目
              </button>
            )}
          </div>
        )}
        {items.length > 0 && <ApplicationTable items={items} onSelect={setSelected} />}
      </section>

      {createOpen && (
        <CreateApplicationDialog
          isPending={createApplication.isPending}
          error={createApplication.error?.message ?? null}
          onClose={closeCreateDialog}
          onSubmit={submitApplication}
        />
      )}
      {selected && (
        <ApplicationDetail
          application={selected}
          onClose={() => setSelected(null)}
          onUpdated={updateSelected}
        />
      )}
    </div>
  );
}
