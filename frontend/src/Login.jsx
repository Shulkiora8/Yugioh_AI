import React, { useState } from 'react';
import axios from 'axios';
import { User, Lock, ArrowRight, UserPlus } from 'lucide-react';

const API_URL = 'http://localhost:8000';

const Login = ({ onLogin }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        const res = await axios.post(`${API_URL}/register`, { username, password });
        onLogin(res.data.access_token);
      } else {
        // OAuth2 login expects form data
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        
        const res = await axios.post(`${API_URL}/login`, formData);
        onLogin(res.data.access_token);
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Error en la conexión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-overlay">
      <div className="login-card">
        <div className="login-header">
          <h1>YU-GI-OH HELPER</h1>
          <p>{isRegister ? 'Crea tu cuenta de duelista' : 'Bienvenido de nuevo, duelista'}</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="input-group">
            <User size={18} />
            <input 
              type="text" 
              placeholder="Nombre de usuario" 
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required 
            />
          </div>

          <div className="input-group">
            <Lock size={18} />
            <input 
              type="password" 
              placeholder="Contraseña" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required 
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button type="submit" className="login-submit" disabled={loading}>
            {loading ? 'Procesando...' : (isRegister ? 'REGISTRARSE' : 'ENTRAR')}
            {!loading && <ArrowRight size={18} />}
          </button>
        </form>

        <div className="login-footer">
          <button onClick={() => setIsRegister(!isRegister)}>
            {isRegister ? (
              <><User size={14} /> ¿Ya tienes cuenta? Inicia sesión</>
            ) : (
              <><UserPlus size={14} /> ¿No tienes cuenta? Regístrate</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Login;
