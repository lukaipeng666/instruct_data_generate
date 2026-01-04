import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import DataEditorPage from './pages/DataEditorPage';
import DataFileEditorPage from './pages/DataFileEditorPage';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function App() {
  const isAdmin = useAuthStore((state) => state.isAdmin);
  
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            {isAdmin ? <AdminDashboardPage /> : <DashboardPage />}
          </PrivateRoute>
        }
      />
      <Route
        path="/editor/:taskId"
        element={
          <PrivateRoute>
            <DataEditorPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/data-editor/:fileId"
        element={
          <PrivateRoute>
            <DataFileEditorPage />
          </PrivateRoute>
        }
      />
    </Routes>
  );
}

export default App;

