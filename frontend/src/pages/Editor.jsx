import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import CodeEditor from "../components/CodeEditor";
import ChatBox from "../components/ChatBox";
import OutputPanel from "../components/OutputPanel";
import { api } from "../api";

const EXT_LANG = { py: "python", js: "javascript" };
const STARTER = {
  python: "print('Hello, world!')\n",
  javascript: "console.log('Hello, world!');\n",
};
const langFromName = (name) => EXT_LANG[name.split(".").pop().toLowerCase()] || null;

export default function Editor() {
  const { projectId } = useParams();
  const pid = Number(projectId);

  const [project, setProject] = useState(null);
  const [files, setFiles] = useState([]);
  const [fileId, setFileId] = useState(null);
  const [code, setCode] = useState("");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [runResult, setRunResult] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [aiText, setAiText] = useState("");
  const [aiTitle, setAiTitle] = useState("");

  const startedFor = useRef(null);
  const saveRef = useRef(null);

  const current = files.find((f) => f.id === fileId);
  const language = current ? current.language : "python";

  // Load the project once (the ref stops React StrictMode from loading twice)
  useEffect(() => {
    if (startedFor.current === pid) return;
    startedFor.current = pid;

    async function load() {
      try {
        const p = await api.getProject(pid);
        let fs = await api.listFiles(pid);
        if (fs.length === 0) {
          const f = await api.createFile(pid, {
            filename: "main.py",
            language: "python",
            content: STARTER.python,
          });
          fs = [f];
        }
        setProject(p);
        setFiles(fs);
        setFileId(fs[0].id);
        setCode(fs[0].content);
      } catch (e) {
        setError(e.message);
      }
    }
    load();
  }, [pid]);

  // Ctrl+S saves
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        saveRef.current?.();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  async function save() {
    if (!current || !dirty) return true;
    try {
      const updated = await api.updateFile(pid, current.id, { content: code });
      setFiles((fs) => fs.map((f) => (f.id === updated.id ? updated : f)));
      setDirty(false);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    }
  }
  useEffect(() => {
  saveRef.current = save;
});

  function clearResults() {
    setRunResult(null);
    setAnalysis(null);
    setAiText("");
    setAiTitle("");
  }

  function switchFile(id) {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    const f = files.find((x) => x.id === id);
    setFileId(id);
    setCode(f.content);
    setDirty(false);
    clearResults();
  }

  async function newFile() {
    const name = window.prompt("File name (.py or .js):", "script.py");
    if (!name) return;
    const lang = langFromName(name.trim());
    if (!lang) {
      setError("Use a file name ending in .py or .js");
      return;
    }
    if (!(await save())) return;
    try {
      const f = await api.createFile(pid, {
        filename: name.trim(),
        language: lang,
        content: STARTER[lang],
      });
      setFiles((fs) => [...fs, f]);
      setFileId(f.id);
      setCode(f.content);
      setDirty(false);
      clearResults();
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }

  async function action(label, fn) {
    setError("");
    setBusy(label);
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }

  const handleRun = () =>
    action("Running", async () => {
      const r = await api.run(code, language);
      clearResults();
      setRunResult(r);
    });

  const handleDebug = () =>
    action("Running and debugging", async () => {
      const r = await api.runAndDebug(code, language);
      clearResults();
      setRunResult(r.run);
      setAnalysis(r.analysis);
      setAiTitle("Debug suggestion");
      setAiText(
        r.ai_suggestion ||
          (r.ai_error ? `AI unavailable: ${r.ai_error}` : "No problems found. Your code ran successfully.")
      );
    });

  const handleExplain = () =>
    action("Explaining", async () => {
      const r = await api.explain(code, language);
      clearResults();
      setAiTitle("Explanation");
      setAiText(r.result);
    });

  const handleRefactor = () =>
    action("Refactoring", async () => {
      const r = await api.refactor(code, language);
      clearResults();
      setAiTitle("Refactored code");
      setAiText(r.result);
    });

  function applyFix(newCode) {
    setCode(newCode);
    setDirty(true);
  }

  if (!project) {
    return (
      <div className="page">
        {error ? <div className="error">{error}</div> : <p className="muted">Loading...</p>}
        {error && <Link to="/dashboard">Back to projects</Link>}
      </div>
    );
  }

  const disabled = !!busy;

  return (
    <div className="editor-page">
      <div className="toolbar">
        <Link to="/dashboard">← Projects</Link>
        <strong>{project.name}</strong>
        <select value={fileId} onChange={(e) => switchFile(Number(e.target.value))}>
          {files.map((f) => (
            <option key={f.id} value={f.id}>
              {f.filename}
            </option>
          ))}
        </select>
        <button onClick={newFile}>+ File</button>
        <span className="muted">{language}</span>
        <span className="spacer" />
        <button onClick={save} disabled={!dirty}>
          {dirty ? "Save *" : "Saved"}
        </button>
        <button className="primary" onClick={handleRun} disabled={disabled}>
          Run
        </button>
        <button onClick={handleDebug} disabled={disabled}>
          Run + Debug
        </button>
        <button onClick={handleExplain} disabled={disabled}>
          Explain
        </button>
        <button onClick={handleRefactor} disabled={disabled}>
          Refactor
        </button>
      </div>
      {error && <div className="error banner">{error}</div>}
      <div className="workspace">
        <div className="editor-pane">
          <CodeEditor
            value={code}
            language={language}
            path={`file-${fileId}`}
            onChange={(v) => {
              setCode(v);
              setDirty(true);
            }}
          />
        </div>
        <div className="side-pane">
          <OutputPanel
            runResult={runResult}
            analysis={analysis}
            aiText={aiText}
            aiTitle={aiTitle}
            busy={busy}
            onApply={applyFix}
          />
          <ChatBox projectId={pid} getCode={() => code} language={language} />
        </div>
      </div>
    </div>
  );
}