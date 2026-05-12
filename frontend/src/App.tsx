import { Route, Routes } from 'react-router-dom';
import SignIn from './pages/SignIn';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SignIn />} />
    </Routes>
  );
}
