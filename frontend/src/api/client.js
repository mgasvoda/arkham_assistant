/**
 * API client for backend communication.
 */

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

/**
 * Make a GET request to the API.
 */
export async function get(endpoint, params = {}) {
  const url = new URL(`${API_BASE}${endpoint}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      url.searchParams.append(key, value);
    }
  });
  
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Make a POST request to the API.
 */
export async function post(endpoint, data = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Make a PUT request to the API.
 */
export async function put(endpoint, data = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Make a DELETE request to the API.
 */
export async function del(endpoint) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
}

// Convenience functions for specific endpoints
export const api = {
  cards: {
    search: (params) => get('/cards', params),
    get: (id) => get(`/cards/${id}`),
  },
  
  decks: {
    list: () => get('/decks'),
    get: (id) => get(`/decks/${id}`),
    create: (data) => post('/decks', data),
    update: (id, data) => put(`/decks/${id}`, data),
    delete: (id) => del(`/decks/${id}`),
  },
  
  characters: {
    list: () => get('/characters'),
    get: (id) => get(`/characters/${id}`),
  },
  
  sim: {
    run: (data) => post('/sim/run', data),
  },
  
  chat: {
    send: (data) => post('/chat', data),
  },
};

