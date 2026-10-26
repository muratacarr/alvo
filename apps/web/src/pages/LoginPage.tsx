import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useState } from "react";
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

  async function submit() {
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
      <Card>
        <Typography.Title level={1}>Sign in</Typography.Title>
        <Typography.Paragraph>Welcome to Alvo.</Typography.Paragraph>
        {DEV_LOGIN_ENABLED ? (
          <Form
            layout="vertical"
            onFinish={() => void submit()}
            requiredMark={false}
            noValidate
          >
            {/* Static information, not an alert: it must not be announced as one. */}
            <p className="mb-4 rounded-md bg-amber-50 p-3 text-sm text-amber-900">
              Development sign-in. Real sign-in methods will be added later.
            </p>
            <Form.Item label="Development user name" htmlFor="subject">
              <Input
                id="subject"
                name="subject"
                required
                maxLength={200}
                autoComplete="username"
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
                status={error ? "error" : undefined}
                aria-invalid={error !== null}
                aria-describedby={error ? "login-error" : undefined}
              />
            </Form.Item>
            {error && <Alert id="login-error" type="error" title={error} className="mb-4" />}
            <Button type="primary" htmlType="submit" block disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </Form>
        ) : (
          <Alert type="info" title="Sign-in is not available yet." role="status" />
        )}
      </Card>
    </main>
  );
}
