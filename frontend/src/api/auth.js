import api from "./api";

export const authLogin = async () => {
    const response = await api.get('/auth/login');
    return response.data;
};