import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertCircle, FileSearch, LoaderCircle, Search } from "lucide-react";
import { retrievalApi } from "../api/client";

const exampleQueries = [
  "医疗器械唯一标识信息由谁提交",
  "临床评价可以免于提交什么资料",
  "违反备案要求由哪个部门处罚",
];

export function EvidenceRetrievalPanel() {
  const [query, setQuery] = useState(exampleQueries[0]);
  const search = useMutation({
    mutationFn: (value: string) => retrievalApi.search(value),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (value.length >= 2) search.mutate(value);
  }

  return (
    <section className="evidence-retrieval" aria-label="法规证据检索">
      <div className="evidence-retrieval-head">
        <div>
          <span className="section-kicker">RAG 证据层</span>
          <h2>法规证据检索</h2>
        </div>
        {search.data && (
          <span className="retrieval-runtime">
            {search.data.total} 条证据 · {search.data.elapsed_ms} ms
          </span>
        )}
      </div>
      <form className="retrieval-search" onSubmit={submit}>
        <Search size={18} aria-hidden="true" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="输入注册申报或合规问题"
          aria-label="输入法规证据检索问题"
        />
        <button className="button primary" type="submit" disabled={search.isPending}>
          {search.isPending ? <LoaderCircle className="spin" size={16} /> : <FileSearch size={16} />}
          {search.isPending ? "检索中" : "检索证据"}
        </button>
      </form>
      <div className="retrieval-examples" aria-label="检索示例">
        {exampleQueries.map((example) => (
          <button
            type="button"
            key={example}
            onClick={() => {
              setQuery(example);
              search.mutate(example);
            }}
          >
            {example}
          </button>
        ))}
      </div>
      {search.isError && (
        <div className="retrieval-error">
          <AlertCircle size={16} />
          <span>{search.error.message}</span>
        </div>
      )}
      {search.data && search.data.items.length === 0 && (
        <div className="retrieval-empty">当前知识库中没有找到可引用证据。</div>
      )}
      {search.data && search.data.items.length > 0 && (
        <div className="evidence-results">
          {search.data.items.map((item, index) => (
            <article className="evidence-result" key={item.chunk_id}>
              <div className="evidence-rank">{String(index + 1).padStart(2, "0")}</div>
              <div className="evidence-content">
                <div className="evidence-title">
                  <div>
                    <strong>{item.citation_label}</strong>
                    <span>{item.source_title}</span>
                  </div>
                  <span className="evidence-score">
                    重排 {item.rerank_score.toFixed(3)}
                  </span>
                </div>
                <p>{item.content}</p>
                <div className="evidence-meta">
                  <span>{item.document_number}</span>
                  <span>{item.version_label}</span>
                  <span>坐标 [{item.char_start}, {item.char_end})</span>
                  <span>RRF {item.retrieval_score.toFixed(3)}</span>
                </div>
                {item.matched_terms.length > 0 && (
                  <div className="matched-terms">
                    {item.matched_terms.map((term) => <span key={term}>{term}</span>)}
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
