import React, { useState, useEffect } from 'react'; // Added imports
import { FcGoogle } from "react-icons/fc";
import { HiOutlineShieldCheck } from "react-icons/hi";
import { useNavigate, useSearchParams } from "react-router-dom"; // Added useSearchParams
import logo from "../asset/mahindra-rise.png";
import { API_BASE_URL, SSO_URL } from "../api/api"; // Ensure SSO_URL is exported from here

const LoginPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // --- NEW: Token capture logic ---
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    if (token) {
      localStorage.setItem('auth_token', token);
      urlParams.delete('token');
      const newUrl = `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`;
      window.history.replaceState({}, document.title, newUrl);
      navigate('/dashboard'); // Navigate to your protected route
    }

    const errorParam = searchParams.get('error');
    if (errorParam === 'sso_failed') {
      setError('SSO authentication failed. Please try again or contact IT support.');
    }
  }, [searchParams, navigate]);

  const features = [
    { icon: "🎨", title: "Image Generation", desc: "Create images from text prompts" },
    { icon: "🏆", title: "Model Bake-off", desc: "Compare multiple ML models automatically" },
    { icon: "🔬", title: "What-If Analysis", desc: "Real-time predictions from your models" },
    { icon: "📈", title: "Time-Series", desc: "Advanced ARIMA forecasting" },
  ];

  const handleGoogle = async () => {
    try {
      setLoading(true);
      window.location.href = `${API_BASE_URL}/auth/login`;      
    } catch (error) {
      console.error("Login failed:", error);
      setLoading(false);
    }
  };

  // --- NEW: SSO Login Handler ---
  const handleSSOLogin = () => {
    try {
      setLoading(true);
      window.location.href = SSO_URL;
    } catch (error) {
      console.error('❌ SSO login failed:', error);
      setError('Failed to initiate SSO login.');
      setLoading(false);
    }
  };
  
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="flex flex-col items-center justify-center py-12 px-6">
        <div className="mb-6">
          <div className="bg-red-600 text-white rounded-lg px-6 py-3 text-center text-sm font-semibold shadow-lg" style={{boxShadow: '0 18px 40px rgba(220,38,38,0.18)'}}>
            <div>🚗 Rise Intelligence V4.2 • Gemini</div>
            <div>Advanced Features</div>
          </div>
        </div>

        <img src={logo} alt="Mahindra Rise" className="w-56 mb-10" />

        {/* Display Errors */}
        {error && (
          <div className="w-full max-w-sm mb-4 bg-red-900/30 border border-red-500 text-red-200 px-4 py-3 rounded-lg">
            <p className="text-sm">{error}</p>
          </div>
        )}

        <button className="mb-6 flex items-center gap-3 px-6 py-2 rounded-full border border-red-500/80 text-red-400 hover:bg-red-700/5 transition" disabled>
          <HiOutlineShieldCheck className="text-red-400 text-lg" />
          <span className="uppercase text-sm font-semibold">Secure Access Portal</span>
        </button>

        <div className="w-full max-w-sm space-y-4">
          <button onClick={handleGoogle} disabled={loading} className="flex items-center justify-center gap-3 bg-blue-600 text-white px-3 py-3 rounded-lg shadow-lg w-full hover:scale-[1.01] transition disabled:opacity-50">
            <div className="bg-white rounded-md p-1">
              <FcGoogle className="text-xl" />
            </div>
            <span className="font-medium text-sm">{loading ? 'Redirecting...' : 'Continue with Google'}</span>
          </button>

          {/* --- NEW: Divider & SSO Button --- */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-gray-700"></div>
            <span className="text-xs text-gray-500 uppercase">Or</span>
            <div className="flex-1 h-px bg-gray-700"></div>
          </div>

          <button
            onClick={handleSSOLogin}
            disabled={loading}
            className="flex items-center justify-center gap-3 bg-red-600 text-white px-4 py-3 rounded-lg shadow-lg w-full hover:bg-red-700 hover:scale-[1.02] transition disabled:opacity-50"
          >
            <HiOutlineShieldCheck className="text-xl" />
            <span className="font-medium text-sm">
              {loading ? 'Redirecting...' : 'Sign In With Mahindra SSO'}
            </span>
          </button>
        </div>
      </div>
      
      {/* (Features section remains unchanged below) */}
      {/* ... */}
    </div>
  );
};

export default LoginPage;