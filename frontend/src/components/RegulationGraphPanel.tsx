import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  MoveRight,
  Network,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { regulationsApi } from "../api/client";
import type {
  KnowledgeGraphNode,
  KnowledgeGraphRelationshipType,
} from "../types";

type GraphFilter = "overview" | "scope" | "requirements" | "evidence" | "all";

const nodeTypeLabels: Record<KnowledgeGraphNode["node_type"], string> = {
  regulation_source: "法规来源",
  regulation_version: "法规版本",
  device_scope: "适用范围",
  dossier_requirement: "申报资料",
  legal_chunk: "证据条款",
};

const filterOptions: Array<{
  key: GraphFilter;
  label: string;
  types: KnowledgeGraphRelationshipType[];
}> = [
  {
    key: "overview",
    label: "版本与引用",
    types: ["has_version", "supersedes", "cites"],
  },
  { key: "scope", label: "适用范围", types: ["applies_to"] },
  { key: "requirements", label: "资料要求", types: ["requires"] },
  { key: "evidence", label: "条款证据", types: ["supported_by"] },
  {
    key: "all",
    label: "全部关系",
    types: [
      "has_version",
      "supersedes",
      "cites",
      "applies_to",
      "requires",
      "supported_by",
    ],
  },
];

interface RegulationGraphPanelProps {
  sourceId: string;
}

export function RegulationGraphPanel({ sourceId }: RegulationGraphPanelProps) {
  const [filter, setFilter] = useState<GraphFilter>("overview");
  const queryClient = useQueryClient();
  const graph = useQuery({
    queryKey: ["regulation-graph", sourceId],
    queryFn: () => regulationsApi.getGraph(sourceId),
  });
  const sync = useMutation({
    mutationFn: () => regulationsApi.syncGraph(sourceId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["regulation-graph", sourceId],
      });
    },
  });
  const activeTypes = filterOptions.find((option) => option.key === filter)!.types;
  const relationships = useMemo(
    () =>
      (graph.data?.relationships ?? []).filter((relationship) =>
        activeTypes.includes(relationship.relationship_type),
      ),
    [activeTypes, graph.data?.relationships],
  );
  const nodes = useMemo(
    () => new Map((graph.data?.nodes ?? []).map((node) => [node.id, node])),
    [graph.data?.nodes],
  );
  const verifiedCount =
    graph.data?.relationships.filter((relationship) => relationship.verified).length ?? 0;

  return (
    <section className="knowledge-graph-section" aria-label="法规关系图谱">
      <div className="knowledge-graph-heading">
        <div>
          <span className="eyebrow">Neo4j 关系投影</span>
          <h3>法规关系图谱</h3>
          <p>追踪法规版本、制定依据、适用范围、资料要求与证据条款。</p>
        </div>
        <button
          className="button secondary compact-button"
          type="button"
          disabled={sync.isPending}
          onClick={() => sync.mutate()}
        >
          <RefreshCw size={14} className={sync.isPending ? "spin" : undefined} />
          {sync.isPending ? "同步中" : "同步图谱"}
        </button>
      </div>

      {graph.isLoading && <div className="graph-state">正在读取法规关系…</div>}
      {graph.isError && (
        <div className="graph-state graph-state-error">
          <AlertTriangle size={16} />
          <span>{graph.error.message}</span>
          <button type="button" onClick={() => sync.mutate()} disabled={sync.isPending}>
            立即同步
          </button>
        </div>
      )}

      {graph.data && (
        <>
          <div className="graph-metrics" aria-label="关系图谱指标">
            <div>
              <span>节点</span>
              <strong>{graph.data.node_count}</strong>
            </div>
            <div>
              <span>关系</span>
              <strong>{graph.data.relationship_count}</strong>
            </div>
            <div>
              <span>已核验</span>
              <strong>{verifiedCount}</strong>
            </div>
          </div>

          <div className="graph-filters" role="tablist" aria-label="关系类型">
            {filterOptions.map((option) => {
              const count = graph.data.relationships.filter((relationship) =>
                option.types.includes(relationship.relationship_type),
              ).length;
              return (
                <button
                  key={option.key}
                  type="button"
                  role="tab"
                  aria-selected={filter === option.key}
                  className={filter === option.key ? "active" : undefined}
                  onClick={() => setFilter(option.key)}
                >
                  {option.label}
                  <span>{count}</span>
                </button>
              );
            })}
          </div>

          <div className="graph-relationship-list">
            {relationships.map((relationship) => {
              const source = nodes.get(relationship.source_id);
              const target = nodes.get(relationship.target_id);
              if (!source || !target) return null;
              return (
                <article key={relationship.id} className="graph-relationship-row">
                  <div className="graph-node-summary">
                    <span>{nodeTypeLabels[source.node_type]}</span>
                    <strong>{source.label}</strong>
                  </div>
                  <div className="graph-edge-summary">
                    <MoveRight size={18} aria-hidden="true" />
                    <b>{relationship.label}</b>
                  </div>
                  <div className="graph-node-summary">
                    <span>{nodeTypeLabels[target.node_type]}</span>
                    <strong>{target.label}</strong>
                  </div>
                  <div className="graph-relation-basis">
                    <span>
                      {relationship.verified && <ShieldCheck size={13} />}
                      {relationship.verified ? "已核验" : "待核验"} · {relationship.basis}
                    </span>
                    {relationship.evidence_excerpt && (
                      <p>
                        <Network size={13} />
                        <b>{relationship.evidence_label}</b>
                        {relationship.evidence_excerpt}
                      </p>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
