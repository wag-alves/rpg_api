import { useState, useEffect, useCallback, useRef } from "react";

const URL_GATEWAY = (() => {
  const protocol = window.location.protocol;
  const hostname = window.location.hostname;
  
  if (hostname.includes('.github.dev')) {
    const backendHostname = hostname.replace('5173', '8000');
    return `${protocol}//${backendHostname}`; 
  }

  return `${protocol}//${hostname}:8000`;
})();

const WS_GATEWAY = URL_GATEWAY.replace("http://", "ws://").replace("https://", "wss://");

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
  const [erroAlocacao, setErroAlocacao] = useState(false);

  const [itensLoja, setItensLoja] = useState([]);
  const [abaAtiva, setAbaAtiva] = useState("missoes");
  const [quantidades, setQuantidades] = useState({});
  const [comprando, setComprando] = useState(null);

  const [boss, setBoss] = useState(null);
  const [bossLog, setBossLog] = useState([]);
  const [topDamage, setTopDamage] = useState([]);
  const [reward, setReward] = useState(null);
  const [ataqueCooldown, setAtaqueCooldown] = useState(false);
  const [lobbyFull, setLobbyFull] = useState(false);
  const wsRef = useRef(null);

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
      
      if (!res.ok) {
        // Em caso de erro, tenta extrair mensagem de diferentes locais
        const mensagem = 
          json?.data?.message || 
          json?.message || 
          json?.detail || 
          "Erro na requisição";
        throw new Error(mensagem);
      }
      
      // Retorna os dados (pode estar dentro de .data ou ser direto)
      return json?.data || json;
    },
    [adicionarLog],
  );

  const carregarTudo = useCallback(async () => {
    if (!heroi) return;
    setCarregando(true);
    try {
      const [s, q] = await Promise.all([
        buscarApi("GET", `/api/heroes/${heroi.id}/stats`),
        buscarApi("GET", "/api/quests"),
      ]);
      setEstatisticas(s);
      setMissoes(q.missoes || []);

      try {
        const i = await buscarApi("GET", "/api/shop/items");
        setItensLoja(i.itens || []);
      } catch (_) {}
    } catch (e) {
      mostrarToast(e.message, "error");
    } finally {
      setCarregando(false);
    }
  }, [buscarApi, heroi]);

  useEffect(() => {
    const checkout = async () => {
      try {
        const res = await fetch(`${URL_GATEWAY}/api/heroes/checkout`, { method: "POST" });
        if (res.status === 409) {
          setErroAlocacao(true);
          return;
        }
        const json = await res.json();
        const h = json?.data || json;
        setHeroi(h);
      } catch (e) {
        setErroAlocacao(true);
      }
    };
    checkout();

    return () => {
      if (heroi) {
        navigator.sendBeacon(`${URL_GATEWAY}/api/heroes/${heroi.id}/checkin`, "");
      }
    };
  }, []);

  useEffect(() => {
    if (heroi) {
      carregarTudo();
    }
  }, [heroi, carregarTudo]);

  const aceitarMissao = async (questId) => {
    if (!heroi) return;
    try {
      const res = await buscarApi("POST", `/api/quests/${questId}/accept`, {
        id_heroi: heroi.id,
      });
      mostrarToast(res.message);
      await carregarTudo();
    } catch (e) {
      mostrarToast(e.message, "error");
    }
  };

  const concluirMissao = async (missao) => {
    if (!heroi) return;
    try {
      const res = await buscarApi("POST", `/api/quests/${missao.id}/complete`);
      mostrarToast(res.message);
      await buscarApi("PATCH", `/api/heroes/${heroi.id}/xp`, {
        quantidade: missao.recompensa_xp,
      });
      await carregarTudo();
    } catch (e) {
      mostrarToast(e.message, "error");
    }
  };

  const comprarItemLoja = async (itemId) => {
    if (!heroi) return;
    const qtd = quantidades[itemId] || 1;
    setComprando(itemId);
    try {
      const res = await buscarApi("POST", "/api/shop/buy", {
        hero_id: parseInt(heroi.id),
        item_id: itemId,
        quantidade: qtd,
      });
      mostrarToast(res.message);
      await carregarTudo();
    } catch (e) {
      mostrarToast(e.message, "error");
    } finally {
      setComprando(null);
    }
  };

  const conectarBossWS = useCallback(() => {
    if (!heroi || wsRef.current) return;
    const ws = new WebSocket(`${WS_GATEWAY}/ws/boss?hero_id=${heroi.id}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        switch (msg.type) {
          case "welcome":
            setLobbyFull(false);
            break;
          case "lobby_full":
            setLobbyFull(true);
            break;
          case "boss_spawn":
            setBoss(msg.payload);
            setBossLog([]);
            setReward(null);
            break;
          case "boss_status":
            setBoss(msg.payload);
            break;
          case "boss_hp":
            setBoss((prev) => prev ? { ...prev, hp: msg.payload.hp, max_hp: msg.payload.max_hp } : prev);
            setBossLog((prev) => [`⚔️ ${msg.payload.attacker_name} causou ${msg.payload.damage} de dano!`, ...prev].slice(0, 20));
            break;
          case "top_damage":
            setTopDamage(msg.payload || []);
            break;
          case "hero_joined":
            setBossLog((prev) => [`➡️ ${msg.payload.hero_name} entrou na batalha!`, ...prev].slice(0, 20));
            break;
          case "hero_left":
            setBossLog((prev) => [`⬅️ ${msg.payload.hero_name} saiu da batalha!`, ...prev].slice(0, 20));
            break;
          case "boss_defeated":
            setBoss((prev) => prev ? { ...prev, hp: 0, active: false } : prev);
            setBossLog((prev) => [`🏆 Boss derrotado!`, ...prev].slice(0, 20));
            break;
          case "boss_escaped":
            setBoss((prev) => prev ? { ...prev, hp: 0, active: false } : prev);
            setBossLog((prev) => [`💨 O boss escapou!`, ...prev].slice(0, 20));
            break;
          case "reward":
            setReward(msg.payload);
            break;
        }
      } catch (e) {}
    };

    ws.onclose = () => {
      wsRef.current = null;
    };
  }, [heroi]);

  const atacarBoss = async () => {
    if (!wsRef.current || ataqueCooldown) return;
    wsRef.current.send(JSON.stringify({ type: "attack" }));
    setAtaqueCooldown(true);
    setTimeout(() => setAtaqueCooldown(false), 2000);
  };

  const iniciarBoss = async () => {
    try {
      await fetch(`${URL_GATEWAY}/api/boss/spawn`, { method: "POST" });
    } catch (e) {
      mostrarToast("Erro ao iniciar boss", "error");
    }
  };

  useEffect(() => {
    if (heroi && abaAtiva === "boss") {
      conectarBossWS();
    }
    return () => {
      if (wsRef.current && abaAtiva !== "boss") {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [heroi, abaAtiva, conectarBossWS]);

  if (erroAlocacao) {
    return (
      <div style={{ ...styles.root, justifyContent: "center", alignItems: "center", display: "flex" }}>
        <div style={{ textAlign: "center", padding: 80 }}>
          <div style={{ fontSize: 64 }}>🚫</div>
          <h1 style={{ color: "#f87171" }}>Todos os heróis já estão em batalha!</h1>
          <p style={{ color: "#94a3b8", fontSize: 14 }}>
            Os 4 slots estão ocupados. Tente novamente mais tarde.
          </p>
          <p style={{ color: "#555", fontSize: 12, marginTop: 20 }}>
            (Feche a aba se você já está com um herói para liberar o slot)
          </p>
        </div>
      </div>
    );
  }

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

              <div style={styles.gold}>💰 {heroi.gold} ouro</div>

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

        {/* CENTER — QUESTS / SHOP */}
        <main style={styles.main}>
          <div style={styles.tabBar}>
            <button
              style={abaAtiva === "missoes" ? styles.tabAtivo : styles.tab}
              onClick={() => setAbaAtiva("missoes")}
            >
              📜 Missões
            </button>
            <button
              style={abaAtiva === "loja" ? styles.tabAtivo : styles.tab}
              onClick={() => setAbaAtiva("loja")}
            >
              🏪 Loja
            </button>
            <button
              style={abaAtiva === "boss" ? styles.tabAtivo : styles.tab}
              onClick={() => setAbaAtiva("boss")}
            >
              🔥 Chefe
            </button>
          </div>

          {abaAtiva === "missoes" ? (
            <>
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
            </>
          ) : abaAtiva === "loja" ? (
            <>
              <h2 style={styles.sectionTitle}>🏪 Loja de Itens</h2>
              <div style={styles.questList}>
                {itensLoja.length === 0 ? (
                  <div style={styles.skeleton}>Nenhum item disponível...</div>
                ) : (
                  itensLoja.map((item) => (
                    <CartaoItemLoja
                      key={item.id}
                      item={item}
                      quantidade={quantidades[item.id] || 1}
                      comprando={comprando}
                      onQuantidadeChange={(id, val) =>
                        setQuantidades((prev) => ({ ...prev, [id]: val }))
                      }
                      onComprar={comprarItemLoja}
                    />
                  ))
                )}
              </div>
            </>
          ) : (
            <>
              <h2 style={styles.sectionTitle}>🔥 World Boss</h2>
              {lobbyFull ? (
                <div style={styles.skeleton}>
                  Os 4 heróis já estão em batalha! Aguarde um slot liberar...
                </div>
              ) : !boss || !boss.active ? (
                <div style={{ textAlign: "center", marginTop: 40 }}>
                  {reward ? (
                    <div style={styles.rewardCard}>
                      <div style={{ fontSize: 48 }}>🏆</div>
                      <h3 style={{ color: "#f5c518", margin: "12px 0 4px" }}>Boss Derrotado!</h3>
                      <p style={{ color: "#e8e6f0" }}>{reward.hero_name}</p>
                      <p style={{ color: "#4ade80" }}>✨ +{reward.xp} XP</p>
                      <p style={{ color: "#facc15" }}>💰 +{reward.gold} Ouro</p>
                    </div>
                  ) : (
                    <>
                      <p style={{ color: "#94a3b8", marginBottom: 20 }}>
                        Nenhum boss ativo no momento.
                      </p>
                      <button style={styles.btnSpawn} onClick={iniciarBoss}>
                        🔥 Invocar Boss
                      </button>
                    </>
                  )}
                </div>
              ) : (
                <div>
                  <div style={styles.bossHpSection}>
                    <div style={styles.bossName}>{boss.name}</div>
                    <div style={styles.bossHpBar}>
                      <div
                        style={{
                          ...styles.bossHpFill,
                          width: `${(boss.hp / boss.max_hp) * 100}%`,
                          background:
                            boss.hp / boss.max_hp > 0.5
                              ? "#4ade80"
                              : boss.hp / boss.max_hp > 0.25
                              ? "#facc15"
                              : "#f87171",
                        }}
                      />
                    </div>
                    <div style={styles.bossHpText}>
                      {boss.hp} / {boss.max_hp} HP
                    </div>
                    <div style={styles.bossTimer}>⏱ {boss.timer}s</div>
                  </div>

                  <div style={styles.bossActions}>
                    <button
                      style={{
                        ...styles.btnAttack,
                        opacity: ataqueCooldown ? 0.5 : 1,
                      }}
                      onClick={atacarBoss}
                      disabled={ataqueCooldown}
                    >
                      {ataqueCooldown ? "⏳" : "⚔️"} ATACAR
                    </button>
                  </div>

                  <div style={styles.bossContent}>
                    <div style={styles.leaderboardSection}>
                      <h3 style={styles.bossSubtitle}>🏆 Top Dano</h3>
                      {topDamage.length === 0 ? (
                        <p style={{ color: "#555", fontSize: 12 }}>Nenhum dano ainda...</p>
                      ) : (
                        topDamage.map((entry, i) => (
                          <div key={i} style={styles.leaderboardRow}>
                            <span style={styles.rankBadge}>
                              {i === 0 ? "👑" : i === 1 ? "🥈" : i === 2 ? "🥉" : `#${i + 1}`}
                            </span>
                            <span style={{ flex: 1, fontWeight: 600 }}>{entry.name}</span>
                            <span style={{ color: "#888", fontSize: 12 }}>{entry.class}</span>
                            <span style={{ color: "#facc15", fontWeight: 700, marginLeft: 12 }}>
                              {entry.damage}
                            </span>
                            <span style={{ color: "#555", fontSize: 11, marginLeft: 4 }}>
                              ({entry.pct.toFixed(1)}%)
                            </span>
                          </div>
                        ))
                      )}
                    </div>

                    <div style={styles.bossLogSection}>
                      <h3 style={styles.bossSubtitle}>📋 Eventos</h3>
                      <div style={styles.bossLogScroll}>
                        {bossLog.map((entry, i) => (
                          <div key={i} style={styles.bossLogEntry}>{entry}</div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
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

const COR_RARIDADE = {
  Comum: "#94a3b8",
  Raro: "#60a5fa",
  Épico: "#a78bfa",
};

function CartaoItemLoja({ item, quantidade, comprando, onQuantidadeChange, onComprar }) {
  const corRaridade = COR_RARIDADE[item.raridade] || "#aaa";
  const carregando = comprando === item.id;
  return (
    <div style={styles.lojaCard}>
      <div style={styles.lojaHeader}>
        <span style={styles.lojaIcon}>🔹</span>
        <div style={{ flex: 1 }}>
          <div style={styles.questTitle}>{item.nome}</div>
        </div>
        <span
          style={{
            ...styles.badge,
            color: corRaridade,
            borderColor: corRaridade,
          }}
        >
          {item.raridade}
        </span>
        <div style={styles.lojaPreco}>{item.preco}💰</div>
      </div>
      <div style={styles.lojaFooter}>
        <div style={styles.lojaQtd}>
          <button
            style={styles.qtdBtn}
            onClick={() => onQuantidadeChange(item.id, Math.max(1, quantidade - 1))}
            disabled={carregando}
          >
            −
          </button>
          <span style={styles.qtdVal}>{quantidade}</span>
          <button
            style={styles.qtdBtn}
            onClick={() => onQuantidadeChange(item.id, quantidade + 1)}
            disabled={carregando}
          >
            +
          </button>
        </div>
        <button
          style={carregando ? styles.btnComprarDisabled : styles.btnComprar}
          onClick={() => onComprar(item.id)}
          disabled={carregando}
        >
          {carregando ? "⏳" : "🛒 Comprar"}
        </button>
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
  tabBar: {
    display: "flex",
    gap: 0,
    marginBottom: 16,
    borderBottom: "2px solid #2e2b4a",
  },
  tab: {
    background: "transparent",
    border: "none",
    borderBottom: "2px solid transparent",
    color: "#666",
    padding: "8px 16px",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 600,
    marginBottom: -2,
  },
  tabAtivo: {
    background: "transparent",
    border: "none",
    borderBottom: "2px solid #f5c518",
    color: "#f5c518",
    padding: "8px 16px",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 600,
    marginBottom: -2,
  },
  lojaCard: {
    background: "#131222",
    border: "1px solid #1e1c35",
    borderRadius: 10,
    padding: 16,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  lojaHeader: {
    display: "flex",
    gap: 12,
    alignItems: "center",
  },
  lojaIcon: { fontSize: 24 },
  lojaPreco: { fontSize: 16, fontWeight: 700, color: "#facc15", whiteSpace: "nowrap" },
  lojaFooter: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  lojaQtd: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  qtdBtn: {
    background: "#1e1c35",
    border: "1px solid #2e2b4a",
    color: "#e8e6f0",
    borderRadius: 4,
    width: 28,
    height: 28,
    cursor: "pointer",
    fontSize: 16,
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  qtdVal: {
    fontSize: 16,
    fontWeight: 600,
    color: "#e8e6f0",
    width: 24,
    textAlign: "center",
  },
  btnComprar: {
    background: "#1e3a5f",
    border: "1px solid #60a5fa",
    color: "#60a5fa",
    borderRadius: 6,
    padding: "6px 14px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
  },
  btnComprarDisabled: {
    background: "#1a1830",
    border: "1px solid #2e2b4a",
    color: "#555",
    borderRadius: 6,
    padding: "6px 14px",
    cursor: "not-allowed",
    fontSize: 13,
    fontWeight: 600,
  },
  btnSpawn: {
    background: "#5f1a1a",
    border: "1px solid #f87171",
    color: "#f87171",
    borderRadius: 8,
    padding: "12px 28px",
    cursor: "pointer",
    fontSize: 16,
    fontWeight: 700,
  },
  bossHpSection: {
    background: "#1a1830",
    border: "1px solid #2e2b4a",
    borderRadius: 10,
    padding: 16,
    marginBottom: 16,
  },
  bossName: {
    fontSize: 18,
    fontWeight: 700,
    color: "#f87171",
    marginBottom: 8,
    textAlign: "center",
  },
  bossHpBar: {
    height: 20,
    background: "#1e1c35",
    borderRadius: 10,
    overflow: "hidden",
  },
  bossHpFill: {
    height: "100%",
    borderRadius: 10,
    transition: "width 0.3s ease, background 0.3s ease",
  },
  bossHpText: {
    textAlign: "center",
    fontSize: 14,
    color: "#e8e6f0",
    marginTop: 6,
  },
  bossTimer: {
    textAlign: "center",
    fontSize: 12,
    color: "#888",
    marginTop: 4,
  },
  bossActions: {
    display: "flex",
    justifyContent: "center",
    marginBottom: 16,
  },
  btnAttack: {
    background: "#5f1a1a",
    border: "2px solid #f87171",
    color: "#f87171",
    borderRadius: 50,
    padding: "16px 48px",
    cursor: "pointer",
    fontSize: 18,
    fontWeight: 700,
    transition: "all 0.2s",
  },
  bossContent: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 16,
  },
  bossSubtitle: {
    fontSize: 14,
    color: "#f5c518",
    margin: "0 0 8px",
  },
  leaderboardSection: {
    background: "#131222",
    border: "1px solid #1e1c35",
    borderRadius: 10,
    padding: 12,
  },
  leaderboardRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 0",
    borderBottom: "1px solid #1e1c35",
    fontSize: 13,
  },
  rankBadge: { fontSize: 16, width: 28, textAlign: "center" },
  bossLogSection: {
    background: "#131222",
    border: "1px solid #1e1c35",
    borderRadius: 10,
    padding: 12,
    display: "flex",
    flexDirection: "column",
  },
  bossLogScroll: {
    maxHeight: 200,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  bossLogEntry: {
    fontSize: 12,
    color: "#94a3b8",
    padding: "3px 6px",
    background: "#0a0912",
    borderRadius: 4,
  },
  rewardCard: {
    background: "#1a1830",
    border: "2px solid #f5c518",
    borderRadius: 12,
    padding: 24,
    display: "inline-block",
    textAlign: "center",
  },
};
