import { useState, useEffect, useCallback } from "react";

const URL_GATEWAY = `${window.location.protocol}//${window.location.hostname.replace("5173","8000")}`;
const ID_HEROI = "1";

const COR_DIFICULDADE = {
  Fácil: "#4ade80",
  Médio: "#facc15",
  Épico: "#f87171",
};

const ROTULO_STATUS = {
  available: "Disponível",
  in_progress: "Em Progresso",
  completed: "Concluída",
};

const COR_STATUS = {
  available: "#60a5fa",
  in_progress: "#facc15",
  completed: "#4ade80",
};

export default function App() {
  const [heroi, setHeroi] = useState(null);
  const [estatisticas, setEstatisticas] = useState(null);
  const [missoes, setMissoes] = useState([]);
  const [logs, setLogs] = useState([]);
  const [carregando, setCarregando] = useState(false);
  const [toast, setToast] = useState(null);

  const adicionarLog = useCallback((method, path, status, payload) => {
    const entry = {
      id: Date.now() + Math.random(),
      time: new Date().toLocaleTimeString("pt-BR"),
      method,
      path,
      status,
      payload: JSON.stringify(payload, null, 2),
    };
    setLogs((prev) => [entry, ...prev].slice(0, 30));
  }, []);

  const mostrarToast = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const buscarApi = useCallback(
    async (method, path, body = null) => {
      const url = `${URL_GATEWAY}${path}`;
      const opts = {
        method,
        headers: { "Content-Type": "application/json" },
        ...(body ? { body: JSON.stringify(body) } : {}),
      };
      const res = await fetch(url, opts);
      const json = await res.json();
      adicionarLog(method, path, res.status, json);
      if (!res.ok) throw new Error(json.detail || "Erro na requisição");
      return json.data;
    },
    [adicionarLog],
  );

  const carregarTudo = useCallback(async () => {
    setCarregando(true);
    try {
      const [h, s, q] = await Promise.all([
        buscarApi("GET", `/api/heroes/${ID_HEROI}`),
        buscarApi("GET", `/api/heroes/${ID_HEROI}/stats`),
        buscarApi("GET", "/api/quests"),
      ]);
      setHeroi(h);
      setEstatisticas(s);
      setMissoes(q.missoes || []);
    } catch (e) {
      mostrarToast(e.message, "error");
    } finally {
      setCarregando(false);
    }
  }, [buscarApi]);

  useEffect(() => {
    carregarTudo();
  }, [carregarTudo]);

  const aceitarMissao = async (questId) => {
    try {
      const res = await buscarApi("POST", `/api/quests/${questId}/accept`, {
        id_heroi: ID_HEROI,
      });
      mostrarToast(res.message);
      await carregarTudo();
    } catch (e) {
      mostrarToast(e.message, "error");
    }
  };

  const concluirMissao = async (missao) => {
    try {
      const res = await buscarApi("POST", `/api/quests/${missao.id}/complete`);
      mostrarToast(res.message);
      await buscarApi("PATCH", `/api/heroes/${ID_HEROI}/xp`, {
        quantidade: missao.recompensa_xp,
      });
      await carregarTudo();
    } catch (e) {
      mostrarToast(e.message, "error");
    }
  };

  const pct_xp = heroi ? Math.round((heroi.xp / heroi.xp_next) * 100) : 0;
  const pct_vida = heroi ? Math.round((heroi.hp / heroi.max_hp) * 100) : 0;
  const pct_mana = heroi ? Math.round((heroi.mp / heroi.max_mp) * 100) : 0;

  return (
    <div style={styles.root}>
      {/* HEADER */}
      <header style={styles.header}>
        <span style={styles.headerTitle}>⚔️ Quadro de Missões</span>
      </header>

      {/* TOAST */}
      {toast && (
        <div
          style={{
            ...styles.toast,
            background: toast.type === "error" ? "#ef4444" : "#22c55e",
          }}
        >
          {toast.msg}
        </div>
      )}

      <div style={styles.body}>
        {/* LEFT — HERO */}
        <aside style={styles.sidebar}>
          {heroi ? (
            <div style={styles.heroCard}>
              <div style={styles.heroAvatar}>{heroi.avatar}</div>
              <div style={styles.heroName}>{heroi.nome}</div>
              <div style={styles.heroClass}>{heroi.nome_classe}</div>
              <div style={styles.heroLevel}>Nível {heroi.nivel}</div>

              <div style={styles.bars}>
                <Barra
                  label="HP"
                  value={heroi.hp}
                  max={heroi.max_hp}
                  pct={pct_vida}
                  color="#ef4444"
                />
                <Barra
                  label="MP"
                  value={heroi.mp}
                  max={heroi.max_mp}
                  pct={pct_mana}
                  color="#818cf8"
                />
                <Barra
                  label="XP"
                  value={heroi.xp}
                  max={heroi.xp_next}
                  pct={pct_xp}
                  color="#facc15"
                />
              </div>

              <div style={styles.gold}>💰 {heroi.ouro} ouro</div>

              {estatisticas && (
                <div style={styles.statsGrid}>
                  <CaixaEstatistica label="ATK" value={estatisticas.atk} icon="⚔️" />
                  <CaixaEstatistica label="DEF" value={estatisticas.def_} icon="🛡️" />
                  <CaixaEstatistica label="SPD" value={estatisticas.spd} icon="💨" />
                  <CaixaEstatistica label="INT" value={estatisticas.int_} icon="🧠" />
                </div>
              )}
            </div>
          ) : (
            <div style={styles.skeleton}>Carregando herói...</div>
          )}
        </aside>

        {/* CENTER — QUESTS */}
        <main style={styles.main}>
          <h2 style={styles.sectionTitle}>📜 Mural de Missões</h2>
          <div style={styles.questList}>
            {missoes.map((missao) => (
              <CartaoMissao
                key={missao.id}
                missao={missao}
                onAccept={aceitarMissao}
                onComplete={concluirMissao}
              />
            ))}
          </div>
        </main>

        {/* RIGHT — LOG */}
        <aside style={styles.logPanel}>
          <h3 style={styles.logTitle}>🔌 API Log</h3>
          <div style={styles.logScroll}>
            {logs.length === 0 && (
              <div style={styles.logEmpty}>Nenhuma requisição ainda...</div>
            )}
            {logs.map((l) => (
              <EntradaLog key={l.id} log={l} />
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Barra({ label, value, max, pct, color }) {
  return (
    <div style={styles.barRow}>
      <span style={styles.barLabel}>{label}</span>
      <div style={styles.barTrack}>
        <div
          style={{ ...styles.barFill, width: `${pct}%`, background: color }}
        />
      </div>
      <span style={styles.barVal}>
        {value}/{max}
      </span>
    </div>
  );
}

function CaixaEstatistica({ label, value, icon }) {
  return (
    <div style={styles.statBox}>
      <span>{icon}</span>
      <span style={styles.statVal}>{value ?? "—"}</span>
      <span style={styles.statLabel}>{label}</span>
    </div>
  );
}

function CartaoMissao({ missao, onAccept, onComplete }) {
  const corDificuldade = COR_DIFICULDADE[missao.dificuldade] || "#aaa";
  const corStatus = COR_STATUS[missao.status] || "#aaa";

  return (
    <div style={styles.questCard}>
      <div style={styles.questHeader}>
        <span style={styles.questIcon}>{missao.icone}</span>
        <div style={{ flex: 1 }}>
          <div style={styles.questTitle}>{missao.titulo}</div>
          <div style={styles.questDesc}>{missao.descricao}</div>
        </div>
        <div style={styles.questMeta}>
          <span
            style={{
              ...styles.badge,
              color: corDificuldade,
              borderColor: corDificuldade,
            }}
          >
            {missao.dificuldade}
          </span>
          <span
            style={{
              ...styles.badge,
              color: corStatus,
              borderColor: corStatus,
            }}
          >
            {ROTULO_STATUS[missao.status]}
          </span>
        </div>
      </div>

      <div style={styles.questFooter}>
        <span style={styles.reward}>✨ {missao.recompensa_xp} XP</span>
        <span style={styles.reward}>💰 {missao.recompensa_ouro} ouro</span>
        <div style={{ marginLeft: "auto" }}>
          {missao.status === "available" && (
            <button style={styles.btnAccept} onClick={() => onAccept(missao.id)}>
              ⚔️ Aceitar
            </button>
          )}
          {missao.status === "in_progress" && (
            <button
              style={styles.btnComplete}
              onClick={() => onComplete(missao)}
            >
              ✅ Concluir
            </button>
          )}
          {missao.status === "completed" && (
            <span style={styles.doneLabel}>🏆 Completa</span>
          )}
        </div>
      </div>
    </div>
  );
}

function EntradaLog({ log }) {
  const [open, setOpen] = useState(false);
  const methodColor =
    {
      GET: "#60a5fa",
      POST: "#4ade80",
      PATCH: "#facc15",
      DELETE: "#f87171",
    }[log.method] || "#aaa";
  const ok = log.status < 400;

  return (
    <div style={styles.logEntry} onClick={() => setOpen((o) => !o)}>
      <div style={styles.logLine}>
        <span style={{ ...styles.logMethod, color: methodColor }}>
          {log.method}
        </span>
        <span style={styles.logPath}>{log.path}</span>
        <span
          style={{ ...styles.logStatus, color: ok ? "#4ade80" : "#f87171" }}
        >
          {log.status}
        </span>
        <span style={styles.logTime}>{log.time}</span>
      </div>
      {open && <pre style={styles.logPayload}>{log.payload}</pre>}
    </div>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = {
  root: {
    minHeight: "100vh",
    background: "#0f0e17",
    color: "#e8e6f0",
    fontFamily: "'Segoe UI', sans-serif",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    background: "#1a1830",
    borderBottom: "1px solid #2e2b4a",
    padding: "12px 24px",
    display: "flex",
    alignItems: "center",
    gap: 16,
  },
  headerTitle: { fontSize: 22, fontWeight: 700, color: "#f5c518" },
  toast: {
    position: "fixed",
    top: 16,
    right: 16,
    zIndex: 999,
    padding: "10px 20px",
    borderRadius: 8,
    color: "#fff",
    fontWeight: 600,
    fontSize: 14,
    boxShadow: "0 4px 20px rgba(0,0,0,0.4)",
  },
  body: {
    flex: 1,
    display: "grid",
    gridTemplateColumns: "260px 1fr 320px",
    gap: 0,
    overflow: "hidden",
  },
  sidebar: {
    background: "#131222",
    borderRight: "1px solid #1e1c35",
    padding: 16,
    overflowY: "auto",
  },
  heroCard: { display: "flex", flexDirection: "column", gap: 10 },
  heroAvatar: { fontSize: 56, textAlign: "center" },
  heroName: {
    fontSize: 20,
    fontWeight: 700,
    textAlign: "center",
    color: "#f5c518",
  },
  heroClass: { fontSize: 13, textAlign: "center", color: "#a78bfa" },
  heroLevel: {
    textAlign: "center",
    background: "#2e2b4a",
    borderRadius: 20,
    padding: "3px 12px",
    fontSize: 13,
    color: "#e8e6f0",
    alignSelf: "center",
  },
  bars: { display: "flex", flexDirection: "column", gap: 6 },
  barRow: { display: "flex", alignItems: "center", gap: 6 },
  barLabel: { width: 24, fontSize: 11, color: "#888" },
  barTrack: {
    flex: 1,
    height: 6,
    background: "#1e1c35",
    borderRadius: 4,
    overflow: "hidden",
  },
  barFill: { height: "100%", borderRadius: 4, transition: "width 0.4s ease" },
  barVal: { fontSize: 10, color: "#666", width: 50, textAlign: "right" },
  gold: { textAlign: "center", fontSize: 14, color: "#facc15" },
  statsGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 },
  statBox: {
    background: "#1a1830",
    border: "1px solid #2e2b4a",
    borderRadius: 8,
    padding: 8,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 2,
  },
  statVal: { fontSize: 18, fontWeight: 700, color: "#e8e6f0" },
  statLabel: { fontSize: 10, color: "#666" },

  skeleton: { color: "#555", textAlign: "center", marginTop: 40 },
  main: {
    padding: "20px 24px",
    overflowY: "auto",
    background: "#0f0e17",
  },
  sectionTitle: { margin: "0 0 12px", fontSize: 18, color: "#f5c518" },

  questList: { display: "flex", flexDirection: "column", gap: 12 },
  questCard: {
    background: "#131222",
    border: "1px solid #1e1c35",
    borderRadius: 10,
    padding: 16,
    display: "flex",
    flexDirection: "column",
    gap: 10,
    transition: "border-color 0.2s",
  },
  questHeader: { display: "flex", gap: 12, alignItems: "flex-start" },
  questIcon: { fontSize: 28 },
  questTitle: { fontWeight: 700, fontSize: 15, color: "#e8e6f0" },
  questDesc: { fontSize: 13, color: "#888", marginTop: 2 },
  questMeta: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    alignItems: "flex-end",
  },
  badge: {
    fontSize: 11,
    border: "1px solid",
    borderRadius: 20,
    padding: "2px 8px",
    whiteSpace: "nowrap",
  },
  questFooter: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap",
  },
  reward: { fontSize: 13, color: "#a78bfa" },
  tag: {
    fontSize: 11,
    background: "#1a1830",
    border: "1px solid #2e2b4a",
    borderRadius: 4,
    padding: "2px 6px",
    color: "#666",
  },
  btnAccept: {
    background: "#1e3a5f",
    border: "1px solid #60a5fa",
    color: "#60a5fa",
    borderRadius: 6,
    padding: "6px 14px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
  },
  btnComplete: {
    background: "#14432a",
    border: "1px solid #4ade80",
    color: "#4ade80",
    borderRadius: 6,
    padding: "6px 14px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
  },
  doneLabel: { fontSize: 13, color: "#4ade80" },
  logPanel: {
    background: "#0a0912",
    borderLeft: "1px solid #1e1c35",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  logTitle: {
    margin: 0,
    padding: "12px 16px",
    fontSize: 14,
    borderBottom: "1px solid #1e1c35",
    color: "#f5c518",
  },
  logScroll: { flex: 1, overflowY: "auto", padding: 8 },
  logEmpty: { color: "#444", fontSize: 12, textAlign: "center", marginTop: 20 },
  logEntry: {
    background: "#131222",
    border: "1px solid #1e1c35",
    borderRadius: 6,
    padding: "6px 8px",
    marginBottom: 6,
    cursor: "pointer",
    fontSize: 12,
  },
  logLine: { display: "flex", gap: 6, alignItems: "center" },
  logMethod: { fontWeight: 700, width: 40, fontSize: 11 },
  logPath: {
    flex: 1,
    color: "#aaa",
    fontSize: 11,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  logStatus: { fontWeight: 700, fontSize: 11 },
  logTime: { color: "#444", fontSize: 10 },
  logPayload: {
    marginTop: 6,
    fontSize: 10,
    color: "#777",
    background: "#0a0912",
    padding: 6,
    borderRadius: 4,
    overflow: "auto",
    maxHeight: 200,
  },
};
