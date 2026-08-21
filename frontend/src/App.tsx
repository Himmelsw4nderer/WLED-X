import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { DevicesPage } from "./pages/DevicesPage";
import { EffectsListPage } from "./pages/EffectsListPage";

// three.js (Builder) and reactflow (EffectEditor) are the bulk of the bundle
// size; route-level splitting keeps them out of the initial load.
const BuilderPage = lazy(() => import("./pages/BuilderPage").then((m) => ({ default: m.BuilderPage })));
const EffectEditorPage = lazy(() =>
  import("./pages/EffectEditorPage").then((m) => ({ default: m.EffectEditorPage })),
);
const ConsolePage = lazy(() => import("./pages/ConsolePage").then((m) => ({ default: m.ConsolePage })));

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/devices" replace />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route
          path="/builder"
          element={
            <Suspense fallback={<div className="page">Loading…</div>}>
              <BuilderPage />
            </Suspense>
          }
        />
        <Route path="/effects" element={<EffectsListPage />} />
        <Route
          path="/effects/:effectId"
          element={
            <Suspense fallback={<div className="page">Loading…</div>}>
              <EffectEditorPage />
            </Suspense>
          }
        />
        <Route
          path="/console"
          element={
            <Suspense fallback={<div className="page">Loading…</div>}>
              <ConsolePage />
            </Suspense>
          }
        />
      </Route>
    </Routes>
  );
}
