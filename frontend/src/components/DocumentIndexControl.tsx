import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, DatabaseZap, LoaderCircle, RefreshCw } from "lucide-react";
import { retrievalApi } from "../api/client";
import type { VectorIndexStatus } from "../types";

const labels: Record<VectorIndexStatus, string> = {
  pending: "待建索引",
  queued: "索引排队",
  processing: "索引构建中",
  completed: "证据可检索",
  failed: "索引失败",
  stale: "索引待更新",
};

const activeStatuses = new Set<VectorIndexStatus>(["queued", "processing"]);

interface DocumentIndexControlProps {
  documentId: string;
}

export function DocumentIndexControl({ documentId }: DocumentIndexControlProps) {
  const queryClient = useQueryClient();
  const index = useQuery({
    queryKey: ["document-vector-index", documentId],
    queryFn: () => retrievalApi.getIndex(documentId),
    refetchInterval: (query) =>
      query.state.data && activeStatuses.has(query.state.data.status) ? 1500 : false,
  });
  const build = useMutation({
    mutationFn: (force: boolean) => retrievalApi.index(documentId, force),
    onSuccess: (data) => {
      queryClient.setQueryData(["document-vector-index", documentId], data);
    },
  });
  const status = index.data?.status ?? "pending";
  const busy = build.isPending || activeStatuses.has(status);
  const rebuild = status === "completed" || status === "stale" || status === "failed";

  return (
    <div className="document-index-control">
      <span className={`vector-index-status vector-index-${status}`}>
        {busy && <LoaderCircle className="spin" size={12} />}
        {labels[status]}
        {index.data?.indexed_chunk_count
          ? ` · ${index.data.indexed_chunk_count} 条`
          : ""}
      </span>
      {(index.isError || build.isError) && (
        <span
          className="index-error-icon"
          title={index.error?.message ?? build.error?.message}
        >
          <AlertCircle size={14} />
        </span>
      )}
      <button
        className="icon-button subtle"
        type="button"
        title={rebuild ? "重建向量索引" : "构建向量索引"}
        aria-label={rebuild ? "重建向量索引" : "构建向量索引"}
        disabled={busy}
        onClick={() => build.mutate(rebuild)}
      >
        {rebuild ? <RefreshCw size={15} /> : <DatabaseZap size={15} />}
      </button>
    </div>
  );
}
