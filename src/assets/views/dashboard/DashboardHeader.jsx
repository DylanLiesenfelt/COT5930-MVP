const StatusDot = ({ connected }) => (
  <div className={`flex items-center gap-1.5 text-xs font-medium ${connected ? 'text-emerald-600' : 'text-red-600'}`}>
    <span
      className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.6)] animate-pulse' : 'bg-red-500'}`}
    />
    {connected ? 'Connected' : 'Disconnected'}
  </div>
);

const DashboardHeader = ({
  connected, streams, loading, recording, setRecording,
  isElectron, sessionRunning, sessionStarting,
  startSession, stopSession, onRefresh, onAddMonitor,
}) => (
  <header className="flex items-center justify-between px-6 py-3.5 border-b border-slate-200 bg-white flex-shrink-0">
    <div className="flex items-center gap-3">

      <StatusDot connected={connected} />

      {isElectron && (
        <button
          onClick={sessionRunning ? stopSession : startSession}
          disabled={sessionStarting}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-slate-800 border border-slate-800 text-white hover:bg-slate-700 hover:border-slate-700 transition-all disabled:opacity-60 disabled:cursor-wait"
        >
          {sessionStarting ? (
            <>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round">
                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"/>
              </svg>
              Starting…
            </>
          ) : sessionRunning ? (
            <>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="#f87171">
                <rect x="4" y="4" width="16" height="16" rx="2"/>
              </svg>
              Stop Session
            </>
          ) : (
            <>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="#4ade80">
                <polygon points="6,4 20,12 6,20"/>
              </svg>
              Start Session
            </>
          )}
        </button>
      )}

      <button
        onClick={() => setRecording((r) => !r)}
        disabled={!connected}
        className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-slate-800 border border-slate-800 text-white hover:bg-slate-700 hover:border-slate-700 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <span className={`w-2 h-2 rounded-full ${recording ? 'bg-red-400' : 'bg-slate-400'}`} />
        {recording ? 'Recording' : 'Record'}
      </button>
    </div>

    <div className="flex items-center gap-2.5">
      <span className="text-xs text-slate-400 font-normal mr-1">
        {streams.length} stream{streams.length !== 1 ? 's' : ''} detected
      </span>

      <button
        onClick={onRefresh}
        disabled={loading}
        className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-slate-800 border border-slate-800 text-white hover:bg-slate-700 hover:border-slate-700 transition-all disabled:opacity-60 disabled:cursor-wait"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round"
          className={loading ? 'animate-spin' : ''}
        >
          <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"/>
        </svg>
        {loading ? 'Scanning…' : 'Refresh'}
      </button>

      <button
        onClick={onAddMonitor}
        className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-slate-800 border border-slate-800 text-white hover:bg-slate-700 hover:border-slate-700 transition-all"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        Add Monitor
      </button>
    </div>
  </header>
);

export default DashboardHeader;
