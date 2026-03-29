import React, { useEffect, useState } from 'react';
import { collection, query, where, onSnapshot, updateDoc, doc, arrayUnion } from 'firebase/firestore';
import { db } from '../api/firebase';
import { useAuthStore } from '../features/auth/store';

export default function AdminNotifications() {
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const user = useAuthStore((state) => state.user);

  useEffect(() => {
    // Only fetch if a user is logged in
    if (!user?.email) return;

    // Listen to Firestore for notifications targeted at this specific user's email
    // that they haven't read yet.
    const q = query(
      collection(db, 'admin_notifications'),
      where('target_admins', 'array-contains', user.email)
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const notifs = [];
      snapshot.forEach((docSnap) => {
        const data = docSnap.data();
        // Only show if the current user hasn't read it yet
        if (!data.read_by?.includes(user.email)) {
          notifs.push({ id: docSnap.id, ...data });
        }
      });
      // Sort newest first
      notifs.sort((a, b) => b.timestamp?.seconds - a.timestamp?.seconds);
      setNotifications(notifs);
    });

    return () => unsubscribe();
  }, [user]);

  const markAsRead = async (notificationId) => {
    try {
      const notifRef = doc(db, 'admin_notifications', notificationId);
      // Add the user's email to the read_by array so it disappears for them
      await updateDoc(notifRef, {
        read_by: arrayUnion(user.email)
      });
    } catch (error) {
      console.error("Failed to mark notification as read", error);
    }
  };

  // If there are no notifications and the dropdown is closed, don't render anything 
  // (keeps the UI clean for non-admins)
  if (notifications.length === 0 && !isOpen) return null;

  return (
    <div className="relative z-50">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-400 hover:text-white transition-colors"
      >
        <i className="fa-solid fa-bell text-xl"></i>
        {notifications.length > 0 && (
          <span className="absolute top-0 right-0 inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-bold leading-none text-white transform translate-x-1/4 -translate-y-1/4 bg-red-600 rounded-full animate-pulse">
            {notifications.length}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-[#121212] border border-gray-700 rounded-xl shadow-2xl overflow-hidden">
          <div className="px-4 py-3 bg-gray-800 border-b border-gray-700 flex justify-between items-center">
            <h3 className="text-sm font-semibold text-white">Agent Feedback Alerts</h3>
          </div>
          
          <div className="max-h-80 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="p-4 text-center text-sm text-gray-500">
                No new alerts.
              </div>
            ) : (
              notifications.map((notif) => (
                <div key={notif.id} className="p-4 border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xs font-bold text-red-400">🚨 Negative Feedback</span>
                    <span className="text-[10px] text-gray-500">
                      {notif.timestamp?.seconds ? new Date(notif.timestamp.seconds * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ''}
                    </span>
                  </div>
                  <p className="text-xs text-gray-300 mb-2">
                    <span className="font-semibold text-gray-400">{notif.user_name}</span> reported an issue in session <span className="font-mono text-[10px] text-gray-500">{notif.session_id.substring(0,8)}...</span>
                  </p>
                  <div className="p-2 bg-black rounded border border-gray-700 text-xs text-gray-400 italic mb-3">
                    "{notif.feedback_text}"
                  </div>
                  <button 
                    onClick={() => markAsRead(notif.id)}
                    className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    Dismiss
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}