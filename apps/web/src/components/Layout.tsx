import { Button, Layout as AntLayout } from "antd";
import { Link, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";

export function Layout() {
  const { state, signOut } = useAuth();
  const role = state.status === "authenticated" ? state.user.role : null;

  return (
    <AntLayout className="min-h-screen !bg-white">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:p-2 focus:text-slate-900"
      >
        Skip to content
      </a>
      <AntLayout.Header className="flex items-center justify-between">
        <Link to="/" className="text-xl font-bold !text-white">
          Alvo
        </Link>
        <div className="flex items-center gap-3 text-sm text-slate-100">
          {role && <span>Signed in as {role}</span>}
          <Button size="small" onClick={() => void signOut()}>
            Sign out
          </Button>
        </div>
      </AntLayout.Header>
      <AntLayout.Content id="main" tabIndex={-1} className="mx-auto w-full max-w-4xl px-4 py-8">
        <Outlet />
      </AntLayout.Content>
    </AntLayout>
  );
}
