import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearToken, getToken } from "../api";

export default function Navbar() {
  useLocation(); // re-render on navigation so the login state stays current
  const navigate = useNavigate();
  const loggedIn = !!getToken();

  function logout() {
    clearToken();
    navigate("/");
  }

  return (
    <nav className="navbar">
      <Link to={loggedIn ? "/dashboard" : "/"} className="brand">
        AI Coding Assistant
      </Link>
      <div className="nav-right">
        {loggedIn && <Link to="/dashboard">Projects</Link>}
        {loggedIn && <button onClick={logout}>Logout</button>}
      </div>
    </nav>
  );
}