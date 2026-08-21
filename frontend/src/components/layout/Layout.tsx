import { NavLink, Outlet } from "react-router-dom";
import "./Layout.css";

const navItems = [
  { to: "/devices", label: "Devices" },
  { to: "/builder", label: "Builder" },
  { to: "/effects", label: "Effects" },
  { to: "/console", label: "Console" },
];

export function Layout() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <span className="app-nav__brand">Lumen</span>
        <div className="app-nav__links">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => "app-nav__link" + (isActive ? " app-nav__link--active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
