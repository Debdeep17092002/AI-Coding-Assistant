import MonacoEditor from "@monaco-editor/react";

export default function CodeEditor({ value, language, path, onChange }) {
  return (
    <MonacoEditor
      height="100%"
      language={language}
      path={path}
      theme="vs-dark"
      value={value}
      onChange={(v) => onChange(v ?? "")}
      options={{
        fontSize: 14,
        minimap: { enabled: false },
        automaticLayout: true,
        scrollBeyondLastLine: false,
        tabSize: 4,
      }}
    />
  );
}