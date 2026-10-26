import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { describeError } from "../errors";

const DEV_LOGIN_ENABLED = import.meta.env.VITE_DEV_LOGIN !== "false";

function messageFor(error: unknown): string {
  if (error instanceof ApiError && error.status === 404) {
    return "Sign-in is not available yet.";
  }
  return describeError(error, "Could not sign in. Please try again.");
}

export function LoginPage() {
  const { state, signIn } = useAuth();
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (state.status === "authenticated") return <Navigate to="/" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    const name = subject.trim();
    if (name === "") {
      setError("Enter a user name.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signIn(name);
    } catch (failure) {
      setError(messageFor(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-8">
      <h1 className="mb-2 text-3xl font-bold text-slate-900">Sign in</h1>
      <p className="mb-6 text-slate-700">Welcome to Alvo.</p>
      {DEV_LOGIN_ENABLED ? (
        <form onSubmit={submit} noValidate className="space-y-4" aria-describedby="login-note">
          <p id="login-note" className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
            Development sign-in. Real sign-in methods will be added later.
          </p>
          <div>
            <label htmlFor="subject" className="mb-1 block font-medium text-slate-900">
              Development user name
            </label>
            <input
              id="subject"
              name="subject"
              type="text"
              required
              maxLength={200}
              autoComplete="username"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              aria-invalid={error !== null}
              aria-describedby={error ? "login-error" : undefined}
              className="w-full rounded-md border border-slate-500 px-3 py-2 text-slate-900"
            />
          </div>
          {error && (
            <p id="login-error" role="alert" className="rounded-md bg-red-50 p-3 text-red-900">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-md bg-indigo-700 px-4 py-2 font-semibold text-white hover:bg-indigo-800 disabled:cursor-wait disabled:opacity-70"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      ) : (
        <p role="status" className="rounded-md bg-slate-100 p-3 text-slate-900">
          Sign-in is not available yet.
        </p>
      )}
    </main>
  );
}
