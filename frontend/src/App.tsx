import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { BuilderPage } from "./pages/BuilderPage";
import { ConsolePage } from "./pages/ConsolePage";
import { DevicesPage } from "./pages/DevicesPage";
import { EffectEditorPage } from "./pages/EffectEditorPage";
import { EffectsListPage } from "./pages/EffectsListPage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/devices" replace />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/builder" element={<BuilderPage />} />
        <Route path="/effects" element={<EffectsListPage />} />
        <Route path="/effects/:effectId" element={<EffectEditorPage />} />
        <Route path="/console" element={<ConsolePage />} />
      </Route>
    </Routes>
  );
}
