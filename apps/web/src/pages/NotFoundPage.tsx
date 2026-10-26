import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="space-y-3">
      <h1 className="text-3xl font-bold text-slate-900">Page not found</h1>
      <p className="text-slate-700">That address does not exist.</p>
      <Link to="/" className="font-medium text-indigo-800 underline">
        Back to projects
      </Link>
    </div>
  );
}
