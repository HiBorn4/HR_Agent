import axios from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_URL;
export const SSO_URL = import.meta.env.VITE_SSO_URL || 'https://ccservices.mahindra.com/auth/login?id=5b5a594d-1aa6-4575-afdd-76c198f7b101&env=PROD';

export const api = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const userInfo = async () => {
    const response = await api.get('/user');
    return response.data;
};

export const callbackUrl = async () => {
    const response = await api.get('/auth/callback');
    return response.data;
};

export const logout = async () => {
    const response = await api.post('/auth/logout');
    return response.data;
};

export const chat = async (payload) => {
    const response = await api.post("/chat", payload);
    return response.data;
};

// Step 1: Upload raw file to Google Cloud Storage
export const uploadFileToGCS = async (formData) => {
    const response = await api.post("/api/upload", formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

// Step 2: Trigger backend processing of the uploaded file
export const fileUpload = async (payload) => {
    const response = await api.post("/api/process_gcs_file", payload);
    return response.data;
};

export const fetchSuggestedQuestions = async () => {
    try {
        const response = await api.get('/api/suggested-questions');
        return response.data;
    } catch (error) {
        console.error("Error fetching suggestions:", error);
        return { data: [] }; // Fail gracefully if backend is down
    }
};

// Step 3: Submit User Feedback (Good/Bad + Text)
export const submitFeedbackAPI = async (payload) => {
    try {
        const response = await api.post("/api/feedback", payload);
        return response.data;
    } catch (error) {
        console.error("Error submitting feedback:", error);
        throw error;
    }
};

export default api;