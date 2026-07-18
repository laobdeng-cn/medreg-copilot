import { useEffect, useRef, type PropsWithChildren } from "react";
import {
  Bot,
  ClipboardCheck,
  FileStack,
  Gauge,
  Library,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, useLocation } from "react-router-dom";
import { securityApi } from "../api/client";

const roleLabels = {
  owner: "租户负责人",
  reviewer: "法规复核人",
  editor: "项目编辑者",
  viewer: "只读观察员",
};

const navItems = [
  { to: "/", label: "工作台", icon: Gauge, end: true },
  { to: "/applications", label: "申报项目", icon: FileStack },
  { to: "/regulations", label: "法规知识库", icon: Library },
  { to: "/precheck", label: "资料预审", icon: ClipboardCheck },
  { to: "/agent", label: "Agent 编制", icon: Bot },
  { to: "/evaluation", label: "评测中心", icon: ShieldCheck },
  { to: "/audit", label: "权限审计", icon: ScrollText },
];

export function AppShell({ children }: PropsWithChildren) {
  const location = useLocation();
  const navigationRef = useRef<HTMLElement>(null);
  const workspace = useQuery({
    queryKey: ["security-workspace"],
    queryFn: securityApi.workspace,
  });
  const actor = workspace.data?.current_actor;

  useEffect(() => {
    navigationRef.current
      ?.querySelector<HTMLElement>("a.active")
      ?.scrollIntoView({ behavior: "auto", block: "nearest", inline: "center" });
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            M
          </div>
          <div>
            <strong>MedReg Copilot</strong>
            <span>医疗器械注册协作</span>
          </div>
        </div>

        <nav ref={navigationRef} className="primary-nav" aria-label="主导航">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => (isActive ? "active" : undefined)}
            >
              <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-foot">
          <ShieldCheck size={17} aria-hidden="true" />
          <span>NMPA 境内 II / III 类</span>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div>
            <span className="environment-dot" aria-hidden="true" />
            MVP 工作区
          </div>
          <div className="topbar-meta">
            <span>{actor ? roleLabels[actor.role] : "身份校验中"}</span>
            <span
              className="avatar"
              title={actor ? `当前用户：${actor.user_name}` : "当前用户"}
            >
              {actor?.user_name.slice(0, 1) ?? "-"}
            </span>
          </div>
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}
