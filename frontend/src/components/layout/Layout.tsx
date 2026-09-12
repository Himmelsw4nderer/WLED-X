import { NavLink, Outlet } from "react-router-dom";
import "./Layout.css";

const navItems = [
  { to: "/builder", label: "Room" },
  { to: "/effects", label: "Patch" },
  { to: "/colors", label: "Colors" },
  { to: "/console", label: "Show" },
  { to: "/devices", label: "Gear" },
];

export function Layout() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <span className="app-nav__brand">
          WLED<span className="app-nav__brand-x">-X</span>
        </span>
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
