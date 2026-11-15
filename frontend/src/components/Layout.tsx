import { BarChart3, BookOpen, Home, LogOut, MessageCircle, Package, Rocket, ShieldAlert, Smartphone, Sparkles, Wallet } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";
import { useT } from "../i18n";
import { LANGS } from "../lib";

const GROUPS = [
  { title: "nav.overview", items: [
    { to: "/", label: "nav.home", icon: Home },
    { to: "/ask", label: "nav.ask", icon: MessageCircle, live: true },
  ] },
  { title: "nav.agents", items: [
    { to: "/insights", label: "nav.insights", icon: BarChart3 },
    { to: "/khata", label: "nav.khata", icon: BookOpen },
    { to: "/inventory", label: "nav.inventory", icon: Package },
    { to: "/growth", label: "nav.growth", icon: Sparkles },
    { to: "/finance", label: "nav.finance", icon: Wallet },
    { to: "/trust", label: "nav.trust", icon: ShieldAlert },
  ] },
  { title: "nav.demo", items: [
    { to: "/phone", label: "nav.phone", icon: Smartphone },
    { to: "/roadmap", label: "nav.roadmap", icon: Rocket },
  ] },
];

export default function Layout() {
  const { merchant, lang, setLang, logout } = useAuth();
  const { t } = useT();
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="flex flex-col bg-gradient-to-b from-paytm-navy via-[#02255a] to-[#031a40] text-white md:sticky md:top-0 md:h-screen md:w-64 md:shrink-0">
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-paytm-blue to-sky-400 text-xl font-bold shadow-lg shadow-sky-900/40">म</div>
          <div>
            <div className="text-lg font-bold leading-tight tracking-tight">Munim AI</div>
            <div className="text-[11px] text-sky-200">{t("app.tagline")}</div>
          </div>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:gap-0 md:overflow-y-auto md:overflow-x-visible">
          {GROUPS.map((g) => (
            <div key={g.title} className="flex shrink-0 gap-1 md:mb-3 md:block md:space-y-0.5">
              <div className="hidden px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-widest text-sky-300/70 md:block">{t(g.title)}</div>
              {g.items.map(({ to, label, icon: Icon, ...rest }) => (
                <NavLink
                  key={to} to={to} end={to === "/"}
                  className={({ isActive }) =>
                    `group relative flex shrink-0 items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition ${isActive ? "bg-white/15 text-white shadow-inner" : "text-sky-100/80 hover:bg-white/10 hover:text-white"}`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && <span className="absolute -left-3 top-1.5 hidden h-6 w-1 rounded-r-full bg-paytm-blue md:block" />}
                      <Icon className="h-4 w-4" />
                      <span>{t(label)}</span>
                      {"live" in rest && <span className="ml-auto hidden h-2 w-2 rounded-full bg-emerald-400 md:block" title={t("nav.voice")} />}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="hidden space-y-2 border-t border-white/10 p-4 text-[11px] text-sky-200/80 md:block">
          <div className="flex flex-wrap gap-1.5">
            {["Sarvam AI", "LangGraph", "Neon"].map((t) => <span key={t} className="rounded-full bg-white/10 px-2 py-0.5">{t}</span>)}
          </div>
          <div>{t("app.footer")}</div>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="glass sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/70 px-5 py-3">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-paytm-navy to-sky-700 text-sm font-bold text-white">
              {merchant?.name.charAt(0)}
            </div>
            <div>
              <div className="text-sm font-semibold leading-tight text-slate-900">{merchant?.name}</div>
              <div className="text-xs text-slate-500">{merchant?.city} · {t("header.merchant")}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div role="group" aria-label={t("header.language")} className="flex rounded-xl bg-slate-100 p-0.5">
              {LANGS.map((l) => (
                <button
                  key={l.code} onClick={() => setLang(l.code)} aria-pressed={lang === l.code}
                  className={`rounded-[10px] px-2.5 py-1 text-xs font-semibold transition ${lang === l.code ? "bg-white text-paytm-navy shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
                >
                  {l.label}
                </button>
              ))}
            </div>
            <button onClick={logout} className="flex items-center gap-1 rounded-lg px-2 py-1 text-sm text-slate-500 transition hover:bg-slate-100 hover:text-slate-800" aria-label={t("header.switchLabel")}>
              <LogOut className="h-4 w-4" /> <span className="hidden sm:inline">{t("header.switch")}</span>
            </button>
          </div>
        </header>
        <main className="mx-auto max-w-7xl p-5 md:p-7"><Outlet /></main>
      </div>
    </div>
  );
}
