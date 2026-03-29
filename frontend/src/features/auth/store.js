import { create } from "zustand";

export const useAuthStore = create((set, get) => ({
  user: null,
  mode: "bigquery",
  login: (userData) => set({ user: userData }),
  logout: () => set({ user: null }),
  isAuthenticated: () => !!get().user,
  setMode: (newMode) => set({ mode: newMode }),
  getUserId: () => get().user?.id || null,
  getUserName: () => get().user?.name || "",
  getUserEmail: () => get().user?.email || "",
  getUserPicture: () => get().user?.picture || "",

  bigqueryMessages: [],
  dynamicMessages: [],

  addMessage: (mode, msg) => {
    if (mode === "bigquery") {
      set((state) => ({
        bigqueryMessages: [...state.bigqueryMessages, msg],
      }));
    } else if (mode === "dynamic") {
      set((state) => ({
        dynamicMessages: [...state.dynamicMessages, msg],
      }));
    }
  },
  
  updateMessage: (mode, id, newMsg) => {
    if (mode === "bigquery") {
      set((state) => ({
        bigqueryMessages: state.bigqueryMessages.map((m) =>
          m.id === id ? { ...m, ...newMsg } : m
        ),
      }));
    } else if (mode === "dynamic") {
      set((state) => ({
        dynamicMessages: state.dynamicMessages.map((m) =>
          m.id === id ? { ...m, ...newMsg } : m
        ),
      }));
    }
  },

  clearMessages: (mode) => {
    if (mode === "bigquery") {
      set({ bigqueryMessages: [] });
    } else if (mode === "dynamic") {
      set({ dynamicMessages: [] });
    }
  },
}));
