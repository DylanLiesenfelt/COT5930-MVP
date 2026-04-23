import { useState, useEffect, useCallback } from 'react';
import Toggle from '../../components/ToggleSwitch';
import { useDevMode } from '../../context/DevModeContext';

const API = 'http://127.0.0.1:8000';

const BLE_FIELDS = [
  { key: 'address',          label: 'BLE Address',         placeholder: 'CB:68:60:DA:76:05' },
  { key: 'device_name',      label: 'Device Name',         placeholder: 'TH21A_CB6860DA7605' },
  { key: 'notify_char_uuid', label: 'Notify Char UUID',    placeholder: '8653000b-…' },
  { key: 'write_char_uuid',  label: 'Write Char UUID',     placeholder: '8653000c-… (optional)' },
  { key: 'service_uuid_hint',label: 'Service UUID Hint',   placeholder: '8653000a-…' },
  { key: 'start_hex',        label: 'Start Command (hex)', placeholder: 'A10001' },
  { key: 'channels',         label: 'Channels',            placeholder: '4' },
  { key: 'sample_rate',      label: 'Sample Rate (Hz)',    placeholder: '128' },
  { key: 'format',           label: 'Format',              placeholder: 'i16le' },
];

const Settings = () => {
  const { devMode, setDevMode } = useDevMode();

  const [sensorsRunning, setSensorsRunning] = useState(false);
  const [sensorsLoading, setSensorsLoading] = useState(false);
  const [bleConfig, setBleConfig] = useState({});
  const [configSaved, setConfigSaved] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API}/sensors/status`);
      const d = await r.json();
      setSensorsRunning(d.running);
    } catch { /* backend may not be ready */ }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const r = await fetch(`${API}/sensors/config`);
      const d = await r.json();
      setBleConfig(d.serenibrain_ble ?? {});
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchConfig();
    const id = setInterval(fetchStatus, 3000);
    return () => clearInterval(id);
  }, [fetchStatus, fetchConfig]);

  const toggleSensors = async () => {
    setSensorsLoading(true);
    try {
      const endpoint = sensorsRunning ? '/sensors/stop' : '/sensors/start';
      await fetch(`${API}${endpoint}`, { method: 'POST' });
      await fetchStatus();
    } catch { /* ignore */ } finally {
      setSensorsLoading(false);
    }
  };

  const handleBleChange = (key, value) => {
    setBleConfig(prev => ({ ...prev, [key]: value }));
  };

  const saveConfig = async () => {
    try {
      await fetch(`${API}/sensors/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ serenibrain_ble: bleConfig }),
      });
      setConfigSaved(true);
      setTimeout(() => setConfigSaved(false), 2000);
    } catch { /* ignore */ }
  };

  return (
    <div className="p-4 space-y-8 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold mb-4">Settings</h1>
        <div className="flex items-center gap-3">
          <span>Development Mode</span>
          <Toggle checked={devMode} onChange={() => setDevMode(!devMode)} />
        </div>
      </div>

      {/* ── Sensors ── */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Sensors</h2>
        <div className="flex items-center gap-4 mb-6">
          <div className={`w-2.5 h-2.5 rounded-full ${sensorsRunning ? 'bg-green-400' : 'bg-gray-500'}`} />
          <span className="text-sm">{sensorsRunning ? 'Running' : 'Stopped'}</span>
          <button
            onClick={toggleSensors}
            disabled={sensorsLoading}
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
              sensorsRunning
                ? 'bg-red-600 hover:bg-red-700 text-white'
                : 'bg-green-600 hover:bg-green-700 text-white'
            } disabled:opacity-50`}
          >
            {sensorsLoading ? '…' : sensorsRunning ? 'Stop Sensors' : 'Start Sensors'}
          </button>
        </div>

        {/* BLE Config */}
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400 mb-2">
          SereniBrain BLE Configuration
        </h3>
        <div className="grid grid-cols-1 gap-3">
          {BLE_FIELDS.map(({ key, label, placeholder }) => (
            <div key={key} className="flex items-center gap-3">
              <label className="w-44 text-sm text-gray-300 shrink-0">{label}</label>
              <input
                type="text"
                value={bleConfig[key] ?? ''}
                placeholder={placeholder}
                onChange={e => handleBleChange(key, e.target.value)}
                className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={saveConfig}
            className="px-4 py-1.5 rounded text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors"
          >
            Save BLE Config
          </button>
          {configSaved && <span className="text-sm text-green-400">Saved!</span>}
        </div>
      </div>
    </div>
  );
};

export default Settings;