import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProjectsPage } from "./pages/ProjectsPage";

// The detail screen pulls in the tree, dialog and select components; load it on demand so the
// sign-in and project list screens stay light.
const ProjectDetailPage = lazy(() =>
  import("./pages/ProjectDetailPage").then((module) => ({ default: module.ProjectDetailPage })),
);

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="/" element={<ProjectsPage />} />
          <Route
            path="/projects/:projectId"
            element={
              <Suspense
                fallback={
                  <p role="status" className="text-slate-700">
                    Loading…
                  </p>
                }
              >
                <ProjectDetailPage />
              </Suspense>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
