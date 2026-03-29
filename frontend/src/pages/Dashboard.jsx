import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import BigQueryView from "../components/BigQueryView";
import DynamicQueryView from "../components/DynamicView";
import { useAuthStore } from "../features/auth/store";
import { userInfo } from "../api/api";

export default function Dashboard() {
  const navigate = useNavigate();
  const mode = useAuthStore((state) => state.mode);
  const setMode = useAuthStore((state) => state.setMode);
  const login = useAuthStore((state) => state.login);
  const user = useAuthStore((state) => state.user);
  
  const [isLoading, setIsLoading] = useState(!user);

  useEffect(() => {
    const checkAuth = async () => {
      if (user) {
        setIsLoading(false);
        return;
      }

      try {
        const response = await userInfo();
        
        if (response && response.id) {
          localStorage.setItem("user_id", response.id);
          
          if (response.session_id) {
            localStorage.setItem("session_id", response.session_id);
          }

          // 🛠️ FIX 1: Enforce BigQuery as the default mode
          setMode("bigquery");
          localStorage.setItem("app_mode", "bigquery");

          login(response); 
        } else {
          throw new Error("User not found in session");
        }
      } catch (err) {
        console.error("Authentication check failed:", err);
        navigate("/login"); 
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, [user, login, navigate, setMode]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-black">
        <div className="text-gray-500">Loading session...</div>
      </div>
    );
  }

  return (
    <div>
      {mode === "bigquery" ? <BigQueryView /> : <DynamicQueryView />}
    </div>
  );
}