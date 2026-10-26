import { Link, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";

export function Layout() {
  const { state, signOut } = useAuth();
  const role = state.status === "authenticated" ? state.user.role : null;

  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-white focus:p-2 focus:text-slate-900"
      >
        Skip to content
      </a>
      <header className="border-b border-slate-300 bg-slate-900">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link to="/" className="text-xl font-bold text-white">
            Alvo
          </Link>
          <div className="flex items-center gap-3 text-sm text-slate-100">
            {role && <span>Signed in as {role}</span>}
            <button
              type="button"
              onClick={() => void signOut()}
              className="rounded-md border border-slate-300 px-3 py-1 font-medium text-white hover:bg-slate-700"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto max-w-4xl px-4 py-8">
        <Outlet />
      </main>
    </>
  );
}
