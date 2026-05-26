import { Route, Routes } from 'react-router-dom';
import AppShell from './components/AppShell';
import SessionPresenceManager from './components/SessionPresenceManager';
import { SessionIdProvider } from './contexts/SessionIdContext';
import Lobby from './pages/Lobby';
import Party from './pages/Party';
import SignIn from './pages/SignIn';

export default function App() {
  return (
    <SessionIdProvider>
      <SessionPresenceManager />
      <AppShell>
        <Routes>
          <Route path="/" element={<SignIn />} />
          <Route path="/lobby" element={<Lobby />} />
          <Route path="/party/:slug" element={<Party />} />
        </Routes>
      </AppShell>
    </SessionIdProvider>
  );
}
