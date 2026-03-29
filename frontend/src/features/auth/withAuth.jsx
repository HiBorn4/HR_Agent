import React from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "./store";

export default function withAuth(WrappedComponent) {
  return function ProtectedComponent(props) {
    const user = useAuthStore((state) => state.user);

    // If user not logged in, redirect to login
    if (!user) {
      return <Navigate to="/login" replace />;
    }

    // If logged in, render the protected component
    return <WrappedComponent {...props} />;
  };
}
