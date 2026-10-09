import ReactMarkdown from "react-markdown";

function extractCode(markdown) {
  const match = markdown.match(/```[\w+-]*\n([\s\S]*?)```/);
  return match ? match[1].replace(/\n$/, "") + "\n" : null;
}

export default function OutputPanel({ runResult, analysis, aiText, aiTitle, busy, onApply }) {
  const issues = analysis?.issues ?? [];
  const fix = aiText ? extractCode(aiText) : null;
  const empty = !runResult && issues.length === 0 && !aiText;

  return (
    <div className="output-panel">
      <div className="panel-title">Output</div>
      <div className="panel-body">
        {busy && <p className="muted">{busy}... (the first AI call can be slow)</p>}
        {empty && !busy && (
          <p className="muted">Run your code or ask the AI. Results appear here.</p>
        )}

        {runResult && (
          <section>
            <div className="meta">
              exit code {runResult.exit_code} · {runResult.duration_ms} ms
              {runResult.timed_out && " · timed out"}
            </div>
            {runResult.stdout && <pre>{runResult.stdout}</pre>}
            {runResult.stderr && <pre className="stderr">{runResult.stderr}</pre>}
            {!runResult.stdout && !runResult.stderr && (
              <p className="muted">(no output)</p>
            )}
          </section>
        )}

        {issues.length > 0 && (
          <section>
            <div className="section-title">Problems</div>
            <ul className="issues">
              {issues.map((i, idx) => (
                <li key={idx} className={i.severity}>
                  {i.line ? `Line ${i.line}: ` : ""}
                  {i.message}
                </li>
              ))}
            </ul>
          </section>
        )}

        {aiText && (
          <section>
            <div className="section-title">{aiTitle || "AI"}</div>
            <div className="markdown">
              <ReactMarkdown>{aiText}</ReactMarkdown>
            </div>
            {fix && (
              <button className="primary" onClick={() => onApply(fix)}>
                Apply code to editor
              </button>
            )}
          </section>
        )}
      </div>
    </div>
  );
}