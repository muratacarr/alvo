import { Alert, Button } from "antd";
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
      <div className="m-8 max-w-md">
        <Alert
          type="error"
          title={describeError(state.error, "Something went wrong. Please try again.")}
          action={<Button onClick={retry}>Try again</Button>}
        />
      </div>
    );
  }
  if (state.status === "anonymous") return <Navigate to="/login" replace />;
  return <Outlet />;
}
