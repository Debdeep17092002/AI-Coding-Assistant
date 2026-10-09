import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, getToken } from "../api";

export default function Home() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (getToken()) return <Navigate to="/dashboard" replace />;

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "register") await api.register(email, password);
      await api.login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page narrow">
      <h1>AI Coding Assistant</h1>
      <p className="muted">Write, run, and debug code with an AI helper.</p>
      <form onSubmit={submit} className="card">
        <h2>{mode === "login" ? "Log in" : "Create account"}</h2>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password (min 8 characters)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <div className="error">{error}</div>}
        <button className="primary" disabled={loading}>
          {loading ? "Please wait..." : mode === "login" ? "Log in" : "Register"}
        </button>
        <button
          type="button"
          className="link"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
          }}
        >
          {mode === "login" ? "Need an account? Register" : "Have an account? Log in"}
        </button>
      </form>
    </div>
  );
}