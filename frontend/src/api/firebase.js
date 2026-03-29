import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
import { getFirestore } from "firebase/firestore";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyCxY9mgwhD-OudmyQrPpaOAWqPHmQN8obk",
  authDomain: "mahindra-datalake-prod-625956.firebaseapp.com",
  projectId: "mahindra-datalake-prod-625956",
  storageBucket: "mahindra-datalake-prod-625956.firebasestorage.app",
  messagingSenderId: "398184046346",
  appId: "1:398184046346:web:45bf33414061237b6ee4f3",
  measurementId: "G-RVVP39FFJ5"
};

// 1. Initialize Firebase App
const app = initializeApp(firebaseConfig);

// 2. Initialize Analytics
export const analytics = typeof window !== "undefined" ? getAnalytics(app) : null;

// 3. Initialize Cloud Firestore
// 🔥 CRITICAL: We pass "aiagent" as the second parameter so it connects to your named database
export const db = getFirestore(app, "aiagent");