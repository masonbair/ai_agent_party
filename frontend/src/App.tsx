import { Route, Routes } from 'react-router-dom';
import Lobby from './pages/Lobby';
import Party from './pages/Party';
import SignIn from './pages/SignIn';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SignIn />} />
      <Route path="/lobby" element={<Lobby />} />
      <Route path="/party/:slug" element={<Party />} />
    </Routes>
  );
}
