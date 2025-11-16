import axios from 'axios';

const rawBaseURL = import.meta.env.VITE_API_URL ?? '/api';
const normalizeBase = (url: string) => {
  if (url === '/') {
    return '/';
  }
  return url.endsWith('/') ? url.slice(0, -1) : url;
};

const baseURL = normalizeBase(rawBaseURL);
const extractionBaseURL = (() => {
  if (baseURL.endsWith('/api')) {
    return baseURL.slice(0, -4) || '/';
  }
  return baseURL || '/';
})();

const createClient = (url: string) => {
  const client = axios.create({ baseURL: url });
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      const message =
        error?.response?.data?.message ??
        error?.message ??
        'Something went wrong';
      return Promise.reject(new Error(message));
    },
  );
  return client;
};

export const apiClient = createClient(baseURL);
export const extractClient = createClient(extractionBaseURL);
