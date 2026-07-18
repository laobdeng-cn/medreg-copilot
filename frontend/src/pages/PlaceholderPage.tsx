import { Clock3 } from "lucide-react";

interface PlaceholderPageProps {
  eyebrow: string;
  title: string;
  description: string;
}

export function PlaceholderPage({
  eyebrow,
  title,
  description,
}: PlaceholderPageProps) {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
      </div>
      <section className="placeholder-panel">
        <Clock3 size={24} aria-hidden="true" />
        <div>
          <strong>已纳入产品路线图</strong>
          <span>当前先完成可验证的项目建档与法规资料基线，再逐步接入智能能力。</span>
        </div>
      </section>
    </div>
  );
}
