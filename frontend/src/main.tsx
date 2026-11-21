import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout";
import { Loading } from "./components/ui";
import { AuthProvider, ToastProvider, useAuth } from "./lib/app";
import Admin from "./pages/Admin";
import Applications, { ApplicationDetail } from "./pages/Applications";
import Assistant from "./pages/Assistant";
import AuthPage from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Interview from "./pages/Interview";
import Jobs, { JobDetail, SavedJobs } from "./pages/Jobs";
import Reminders from "./pages/Reminders";
import Resumes, { ResumeEditor } from "./pages/Resumes";
import Settings from "./pages/Settings";
import Skills from "./pages/Skills";

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <Loading text="Signing you in…" />;
  return user ? <Layout /> : <Navigate to="/login" replace />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/login" element={<AuthPage mode="login" />} />
            <Route path="/register" element={<AuthPage mode="register" />} />
            <Route element={<Protected />}>
              <Route index element={<Dashboard />} />
              <Route path="jobs" element={<Jobs />} />
              <Route path="jobs/:id" element={<JobDetail />} />
              <Route path="saved" element={<SavedJobs />} />
              <Route path="applications" element={<Applications />} />
              <Route path="applications/:id" element={<ApplicationDetail />} />
              <Route path="resumes" element={<Resumes />} />
              <Route path="resumes/:id" element={<ResumeEditor />} />
              <Route path="assistant" element={<Assistant />} />
              <Route path="interview" element={<Interview />} />
              <Route path="skills" element={<Skills />} />
              <Route path="reminders" element={<Reminders />} />
              <Route path="settings" element={<Settings />} />
              <Route path="admin" element={<Admin />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
