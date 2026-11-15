import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setToken, type Lang, type Merchant } from "./api";

interface AuthCtx {
  merchant: Merchant | null;
  loading: boolean;
  lang: Lang;
  setLang: (l: Lang) => void;
  login: (merchantId: number) => Promise<void>;
  logout: () => void;
}
const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [merchant, setMerchant] = useState<Merchant | null>(null);
  const [loading, setLoading] = useState(Boolean(localStorage.getItem("munim_token")));
  const [lang, setLang] = useState<Lang>((localStorage.getItem("munim_lang") as Lang) || "hi");

  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  const logout = useCallback(() => {
    setToken(null);
    setMerchant(null);
  }, []);

  useEffect(() => {
    if (!localStorage.getItem("munim_token")) return;
    api.me().then(setMerchant).catch(logout).finally(() => setLoading(false));
    const h = () => setMerchant(null);
    window.addEventListener("munim-logout", h);
    return () => window.removeEventListener("munim-logout", h);
  }, [logout]);

  const login = useCallback(async (id: number) => {
    const r = await api.login(id);
    setToken(r.token);
    setMerchant(r.merchant);
    const l = (["hi", "mr", "ta", "en"].includes(r.merchant.language) ? r.merchant.language : "hi") as Lang;
    setLang(l);
  }, []);

  const value = useMemo<AuthCtx>(
    () => ({
      merchant, loading, lang, login, logout,
      setLang: (l) => { localStorage.setItem("munim_lang", l); setLang(l); },
    }),
    [merchant, loading, lang, login, logout],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
