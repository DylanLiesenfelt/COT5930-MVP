import { HashRouter, Routes, Route } from 'react-router-dom';
import { useState } from 'react';

import Navbar from './assets/components/Navbar';
import Dashboard from './assets/views/dashboard/Dashboard';
import Settings from './assets/views/settings/Settings';
import MachineLearning from './assets/views/ml/MachineLearning';
import Data from './assets/views/data/Data';

const App = () => {

  const  [devMode, setDevMode] = useState(false);

  return (
    <HashRouter>
      <div className="flex h-screen bg-gray-50">
        <div className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/settings" element={<Settings devMode={devMode} setDevMode={setDevMode} />} />
            <Route path="/ml" element={<MachineLearning />} />
            <Route path="/data" element={<Data />} />
          </Routes>
        </div>
        <Navbar devMode={devMode} />
      </div>
    </HashRouter>
  );
};

export default App;
