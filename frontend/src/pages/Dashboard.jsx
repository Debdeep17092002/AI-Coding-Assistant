import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(e.message));
  }, []);

  async function create(e) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const p = await api.createProject(name.trim());
      setProjects((prev) => [p, ...prev]);
      setName("");
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(id) {
    if (!window.confirm("Delete this project and all its files?")) return;
    try {
      await api.deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <h1>Your projects</h1>
      <form onSubmit={create} className="row">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New project name"
        />
        <button className="primary">Create</button>
      </form>
      {error && <div className="error">{error}</div>}
      {projects.length === 0 && <p className="muted">No projects yet. Create one above.</p>}
      <div className="grid">
        {projects.map((p) => (
          <div key={p.id} className="card">
            <h3>{p.name}</h3>
            <p className="muted">{new Date(p.created_at).toLocaleDateString()}</p>
            <div className="row">
              <Link to={`/editor/${p.id}`} className="button primary">
                Open
              </Link>
              <button onClick={() => remove(p.id)}>Delete</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}