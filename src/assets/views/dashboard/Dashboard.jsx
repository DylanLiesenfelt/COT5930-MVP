import React, { useState, useEffect, useRef, useCallback } from 'react';
import MonitorPanel from './DashboardMonitor';

const WS_URL = 'ws://localhost:8000/ws';
const API_URL = 'http://localhost:8000';



const StatusDot = ({ connected, startState, endState }) => (
  <div style={{
    display: 'flex', alignItems: 'center', gap: 6,
    fontSize: 12, fontWeight: 500,
    color: connected ? '#059669' : '#dc2626',
  }}>
    <div style={{
      width: 7, height: 7, borderRadius: '50%',
      background: connected ? '#10b981' : '#ef4444',
      boxShadow: connected ? '0 0 6px rgba(16,185,129,0.4)' : '0 0 6px rgba(239,68,68,0.4)',
      animation: connected ? 'pulse 2s infinite' : 'none',
    }} />
    {connected ?  `${startState}` : `${endState}` }
  </div>
);

const Dashboard = () => {
  const [monitors, setMonitors] = useState([]);
  const [streams, setStreams] = useState([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const wsRef = useRef(null);
  const dataRef = useRef({});
  const reconnectTimer = useRef(null);
  const manualDisconnect = useRef(false);

  // Session control state
  const [sessionRunning, setSessionRunning] = useState(false);
  const [sessionStarting, setSessionStarting] = useState(false);
  const [backendLogs, setBackendLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);

  const isElectron = !!window.echo;

  /* ── Fetch available streams ────────────────────────── */
  const fetchStreams = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/streams`);
      if (res.ok) {
        const data = await res.json();
        setStreams(data);
      }
    } catch {
      // server might not be up yet
    }
    setLoading(false);
  }, []);

  const refreshStreams = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/refresh`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setStreams(data);
      }
    } catch {
      // server might not be up yet
    }
    setLoading(false);
  }, []);

  /* ── WebSocket connection ───────────────────────────── */
  const connectWs = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= 1) return;
    manualDisconnect.current = false;

    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        setConnected(true);
        fetchStreams();
      };

      ws.onmessage = (evt) => {
        try {
          const pkt = JSON.parse(evt.data);
          const name = pkt.stream;
          if (!dataRef.current[name]) dataRef.current[name] = [];
          dataRef.current[name].push(pkt);
          if (dataRef.current[name].length > 600) {
            dataRef.current[name] = dataRef.current[name].slice(-300);
          }
        } catch { /* ignore parse errors */ }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!manualDisconnect.current) {
          reconnectTimer.current = setTimeout(connectWs, 2000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      reconnectTimer.current = setTimeout(connectWs, 2000);
    }
  }, [fetchStreams]);

  const disconnectWs = useCallback(() => {
    manualDisconnect.current = true;
    setRecording(false);
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    if (wsRef.current) wsRef.current.close();
  }, []);

  /* ── Session control (Electron IPC) ─────────────────── */
  const startSession = useCallback(async () => {
    if (!window.echo) return;
    setSessionStarting(true);
    setBackendLogs([]);

    const result = await window.echo.startSession();
    if (result.ok) {
      setSessionRunning(true);
      // Give the backend time to boot before connecting WebSocket
      setTimeout(() => {
        connectWs();
        setSessionStarting(false);
      }, 2500);
    } else {
      setSessionStarting(false);
      setBackendLogs((prev) => [...prev, `Error: ${result.error}`]);
    }
  }, [connectWs]);

  const stopSession = useCallback(async () => {
    if (!window.echo) return;
    await window.echo.stopSession();
    setSessionRunning(false);
    setRecording(false);
    disconnectWs();
  }, [disconnectWs]);

  // Listen for backend logs and unexpected session stops
  useEffect(() => {
    if (!window.echo) return;

    window.echo.onBackendLog((msg) => {
      setBackendLogs((prev) => {
        const next = [...prev, msg.trim()];
        // Keep last 200 lines
        return next.length > 200 ? next.slice(-200) : next;
      });
    });

    window.echo.onSessionStopped(() => {
      setSessionRunning(false);
      setSessionStarting(false);
      disconnectWs();
    });

    // Check if session was already running (e.g. after hot reload)
    window.echo.sessionStatus().then(({ running }) => {
      if (running) {
        setSessionRunning(true);
        connectWs();
      }
    });
  }, [connectWs, disconnectWs]);

  /* ── Auto-connect WebSocket if not in Electron ──────── */
  useEffect(() => {
    if (!isElectron) {
      connectWs();
    }
    return () => {
      manualDisconnect.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connectWs, isElectron]);

  /* ── Drain consumed data ────────────────────────────── */
  useEffect(() => {
    const interval = setInterval(() => {
      for (const key in dataRef.current) {
        if (dataRef.current[key].length > 2000) {
          dataRef.current[key] = dataRef.current[key].slice(-1000);
        }
      }
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  /* ── Monitor CRUD ───────────────────────────────────── */
  const addMonitor = () => {
    setMonitors((prev) => [
      ...prev,
      { id: uid(), color: SIGNAL_COLORS[prev.length % SIGNAL_COLORS.length] },
    ]);
  };

  const removeMonitor = (id) => {
    setMonitors((prev) => prev.filter((m) => m.id !== id));
  };

  const handleRefresh = async () => {
    await refreshStreams();
  };

  /* ── Button style helper ────────────────────────────── */
  const btnStyle = (bg, border, color, extra = {}) => ({
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '7px 16px', borderRadius: 7,
    background: bg, border: `1px solid ${border}`,
    color, fontSize: 12, fontWeight: 500,
    fontFamily: 'Lexend, sans-serif',
    cursor: 'pointer', transition: 'all 0.15s',
    ...extra,
  });

  return (
    <div style={{
      width: '100%', height: '100vh',
      background: '#f1f5f9',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'Lexend, sans-serif',
      color: '#1e293b',
      overflow: 'hidden',
    }}>
      {/* CSS keyframes */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
      `}</style>

      {/* ── Top Bar ────────────────────────────────────── */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 24px',
        borderBottom: '1px solid #e2e8f0',
        background: '#ffffff',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h1 style={{
            fontSize: 15, fontWeight: 600, letterSpacing: '0.02em',
            color: '#1e293b', margin: 0,
          }}>
            Monitoring Dashboard
          </h1>
          <StatusDot connected={connected} />

          {/* Session control button (Electron only) */}
          {isElectron && (
            <button
              onClick={sessionRunning ? stopSession : startSession}
              disabled={sessionStarting}
              style={btnStyle(
                sessionRunning ? '#fef2f2' : '#f0fdf4',
                sessionRunning ? '#fecaca' : '#bbf7d0',
                sessionRunning ? '#dc2626' : '#15803d',
                { cursor: sessionStarting ? 'wait' : 'pointer' }
              )}
            >
              {sessionStarting ? (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ animation: 'spin 1s linear infinite' }}>
                    <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"/>
                  </svg>
                  Starting…
                </>
              ) : sessionRunning ? (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="4" y="4" width="16" height="16" rx="2"/>
                  </svg>
                  Stop Session
                </>
              ) : (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="6,4 20,12 6,20"/>
                  </svg>
                  Start Session
                </>
              )}
            </button>
          )}

          {/* Backend log toggle (Electron only) */}
          {isElectron && sessionRunning && (
            <button
              onClick={() => setShowLogs((v) => !v)}
              title="Backend logs"
              style={btnStyle(
                showLogs ? '#eff6ff' : '#f8fafc',
                showLogs ? '#bfdbfe' : '#e2e8f0',
                showLogs ? '#2563eb' : '#475569',
              )}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M4 19.5A2.5 2.5 0 016.5 17H20"/>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>
              </svg>
              Logs
              {backendLogs.length > 0 && (
                <span style={{
                  background: '#3b82f6', color: '#fff',
                  borderRadius: 10, padding: '1px 6px',
                  fontSize: 9, fontWeight: 600,
                }}>
                  {backendLogs.length}
                </span>
              )}
            </button>
          )}

          <button
            onClick={() => setRecording((r) => !r)}
            disabled={!connected}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '5px 14px', borderRadius: 7,
              background: recording ? '#fef2f2' : '#f8fafc',
              border: recording ? '1px solid #fecaca' : '1px solid #e2e8f0',
              color: recording ? '#dc2626' : connected ? '#475569' : '#cbd5e1',
              fontSize: 12, fontWeight: 500,
              fontFamily: 'Lexend, sans-serif',
              cursor: connected ? 'pointer' : 'not-allowed',
              transition: 'all 0.15s',
            }}
          >
            <div style={{
              width: 10, height: 10, borderRadius: '50%',
              background: recording ? '#ef4444' : connected ? '#94a3b8' : '#e2e8f0',
              boxShadow: recording ? '0 0 8px rgba(239,68,68,0.5)' : 'none',
              animation: recording ? 'pulse 1.2s infinite' : 'none',
            }} />
            {recording ? 'Recording' : 'Record'}
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontSize: 12, color: '#94a3b8',
            fontWeight: 400, marginRight: 4,
          }}>
            {streams.length} stream{streams.length !== 1 ? 's' : ''} detected
          </span>

          <button
            onClick={handleRefresh}
            disabled={loading}
            style={btnStyle('#f8fafc', '#e2e8f0', '#475569', { cursor: loading ? 'wait' : 'pointer' })}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f1f5f9';
              e.currentTarget.style.borderColor = '#cbd5e1';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#f8fafc';
              e.currentTarget.style.borderColor = '#e2e8f0';
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }}
            >
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"/>
            </svg>
            {loading ? 'Scanning…' : 'Refresh'}
          </button>

          <button
            onClick={addMonitor}
            style={btnStyle('#1e293b', '#1e293b', '#ffffff')}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#334155';
              e.currentTarget.style.borderColor = '#334155';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#1e293b';
              e.currentTarget.style.borderColor = '#1e293b';
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Add Monitor
          </button>
        </div>
      </header>

      {/* ====================================================
                                                Dashboard Grid
      =====================================================*/}
      <div style={{
        flex: 1, overflow: 'auto',
        padding: 20,
      }}>
        {monitors.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            height: '100%', gap: 14, opacity: 0.45,
          }}>
            <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1" strokeLinecap="round">
              <rect x="2" y="3" width="20" height="14" rx="2"/>
              <line x1="8" y1="21" x2="16" y2="21"/>
              <line x1="12" y1="17" x2="12" y2="21"/>
              <polyline points="6 10 9 7 12 11 15 8 18 12" strokeWidth="1.5"/>
            </svg>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4, color: '#475569' }}>
                No monitors active
              </div>
              <div style={{ fontSize: 12, color: '#94a3b8' }}>
                {isElectron && !sessionRunning
                  ? <>Click <strong>Start Session</strong> to launch the backend, then <strong>Add Monitor</strong></>
                  : <>Click <strong>Add Monitor</strong> to start watching a signal stream</>
                }
              </div>
            </div>
          </div>
        ) : (
          <div style={{
            display: 'flex', flexWrap: 'wrap',
            gap: 14, alignContent: 'flex-start',
          }}>
            {monitors.map((m) => (
              <div key={m.id} style={{ animation: 'fadeIn 0.2s ease-out' }}>
                <MonitorPanel
                  id={m.id}
                  streams={streams}
                  dataRef={dataRef}
                  onRemove={removeMonitor}
                  defaultColor={m.color}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ====================================================
                                              Dashboard Footer 
      =====================================================*/}
      <footer style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 24px',
        borderTop: '1px solid #e2e8f0',
        background: '#ffffff',
        fontSize: 11, color: '#94a3b8',
        fontWeight: 400,
        flexShrink: 0,
      }}>
        <span>ECHO v{__APP_VERSION__}</span>
        <div style={{ display: 'flex', gap: 16 }}>
          <span>{monitors.length} monitor{monitors.length !== 1 ? 's' : ''}</span>
        </div>
      </footer>
    </div>
  );
};

export default Dashboard;