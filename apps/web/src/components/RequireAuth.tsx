import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import { describeError } from "../errors";

export function RequireAuth() {
  const { state, retry } = useAuth();

  if (state.status === "loading") {
    return (
      <p role="status" className="p-8 text-slate-700">
        Loading…
      </p>
    );
  }
  if (state.status === "error") {
    return (
      <div role="alert" className="m-8 max-w-md space-y-3 rounded-md bg-red-50 p-4 text-red-900">
        <p>{describeError(state.error, "Something went wrong. Please try again.")}</p>
        <button
          type="button"
          onClick={retry}
          className="rounded-md border border-red-900 px-3 py-1 font-medium"
        >
          Try again
        </button>
      </div>
    );
  }
  if (state.status === "anonymous") return <Navigate to="/login" replace />;
  return <Outlet />;
}
