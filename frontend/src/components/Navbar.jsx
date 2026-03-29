// Hr_fe/src/components/Navbar.jsx
import React, { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FiUser, FiSettings, FiLogOut } from "react-icons/fi";
import logo from "../asset/mahindra-rise.png";
import { logout } from "../api/api";
import { useAuthStore } from "../features/auth/store";
import Cookies from "js-cookie";
import '@fortawesome/fontawesome-free/css/all.min.css';
import AdminNotifications from "./AdminNotifications"; // Import the notifications component

export default function Navbar() {
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef(null);
    const navigate = useNavigate();
    
    // Get store actions
    const user = useAuthStore((state) => state.user);
    const mode = useAuthStore((state) => state.mode);
    const setMode = useAuthStore((state) => state.setMode);
    const clearMessages = useAuthStore((state) => state.clearMessages); // Added to clear session

    const handleLogout = async () => {
        try {
            const response = await logout();
            console.log("Logout response:", response);
            if (!response) {
                throw new Error("Logout request failed");
            }

            Cookies.remove("session_id");
            Cookies.remove("user_id");
            localStorage.removeItem("session_id");
            localStorage.removeItem("user_id");
            navigate("/login");
        } catch (error) {
            console.error("Logout failed:", error);
        }
    };

    // --- NEW: Session Initialization Handlers ---
    const initializeBigQuery = () => {
        setMode("bigquery");
        clearMessages("bigquery"); // Clear chat history for a fresh start
        navigate("/"); // Ensure we are on the dashboard
    };

    const initializeDynamic = () => {
        setMode("dynamic"); // Fixed: Changed from "dynamic_analysis" to "dynamic"
        clearMessages("dynamic"); // Clear chat history for a fresh start
        navigate("/"); // Ensure we are on the dashboard
    };

    useEffect(() => {
        function handleOutside(e) {
            if (menuRef.current && !menuRef.current.contains(e.target)) {
                setMenuOpen(false);
            }
        }
        function handleEsc(e) {
            if (e.key === "Escape") setMenuOpen(false);
        }
        window.addEventListener("click", handleOutside);
        window.addEventListener("keydown", handleEsc);
        return () => {
            window.removeEventListener("click", handleOutside);
            window.removeEventListener("keydown", handleEsc);
        };
    }, []);

    return (
        <nav className="w-full bg-[#0b0b0b] border-b-2 border-red-600/80 ring-1 ring-red-600/10 shadow-sm">
            <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-3">
                <div className="flex items-center gap-4">
                    <img src={logo} alt="Mahindra Rise" className="w-44 h-auto object-contain" />
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={initializeBigQuery}
                        className={`flex items-center gap-2 px-3 py-1 font-bold rounded-full ${
                            mode === "bigquery" ? "bg-red-600" : "bg-gray-700"
                        } hover:bg-red-700 transition`}
                    >
                        <i className="fas fa-database"></i>
                        <span>BigQuery</span>
                    </button>

                    <button
                        onClick={initializeDynamic}
                        className={`flex items-center gap-2 px-3 py-1 font-bold rounded-full ${
                            mode === "dynamic" ? "bg-red-600" : "bg-gray-700"
                        } hover:bg-red-700 transition`}
                    >
                        <i className="fas fa-file-csv"></i>
                        <span>Dynamic Analysis</span>
                    </button>
                </div>


                <div className="flex items-center gap-3">
                    <button className="text-sm px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-full shadow-sm">
                        <i style={{ paddingRight: "20px" }} className="fas fa-brain"></i>
                        AI ENGINE
                    </button>
                    <button className="text-sm px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-full shadow-sm">
                        <i style={{ paddingRight: "25px" }} className="fas fa-robot"></i>
                        AGENT
                    </button>

                    {/* Admin Notifications Bell Component */}
                    <AdminNotifications />

                    <div className="relative" ref={menuRef}>
                        <button
                            onClick={() => setMenuOpen((s) => !s)}
                            aria-expanded={menuOpen}
                            className="w-9 h-9 rounded-full bg-gradient-to-br from-pink-500 to-purple-600 flex items-center justify-center text-white font-semibold focus:outline-none focus:ring-2 focus:ring-red-500"
                        >
                            {user?.picture ? (
                                <img
                                    src={user.picture}
                                    alt={user.name || "User"}
                                    className="w-full h-full object-cover rounded-full"
                                />
                            ) : (
                                <span className="bg-gradient-to-br from-pink-500 to-purple-600 w-full h-full flex items-center justify-center text-white font-semibold rounded-full">
                                    {user?.name ? user.name.charAt(0).toUpperCase() : "A"}
                                </span>
                            )}
                        </button>

                        {menuOpen && (
                            <div className="absolute right-0 mt-3 w-44 bg-[#0e0e0e] border border-gray-800 rounded-lg shadow-lg z-50">
                                <ul className="py-1">
                                    <li>
                                        <button className="w-full text-left flex items-center gap-3 px-4 py-3 text-sm text-gray-200 hover:bg-gray-800">
                                            <FiUser className="text-lg text-gray-300" /> Profile
                                        </button>
                                    </li>
                                    <li>
                                        <button className="w-full text-left flex items-center gap-3 px-4 py-3 text-sm text-gray-200 hover:bg-gray-800">
                                            <FiSettings className="text-lg text-gray-300" /> Settings
                                        </button>
                                    </li>
                                    <li>
                                        <div className="border-t border-gray-800" />
                                    </li>
                                    <li>
                                        <button onClick={handleLogout} className="w-full text-left flex items-center gap-3 px-4 py-3 text-sm text-gray-200 hover:bg-gray-800">
                                            <FiLogOut className="text-lg text-gray-300" /> Logout
                                        </button>
                                    </li>
                                </ul>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </nav>
    );
}