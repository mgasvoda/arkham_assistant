/**
 * API client for backend communication.
 */

import logger from '../utils/logger';

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

  try {
    const response = await fetch(url);
    if (!response.ok) {
      logger.warn(`API GET failed: ${endpoint}`, {
        extra: { status: response.status, statusText: response.statusText },
      });
      throw new Error(`API error: ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    logger.error(`API GET error: ${endpoint}`, { error });
    throw error;
  }
}

/**
 * Make a POST request to the API.
 */
export async function post(endpoint, data = {}) {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      logger.warn(`API POST failed: ${endpoint}`, {
        extra: { status: response.status, statusText: response.statusText },
      });
      throw new Error(`API error: ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    logger.error(`API POST error: ${endpoint}`, { error });
    throw error;
  }
}

/**
 * Make a PUT request to the API.
 */
export async function put(endpoint, data = {}) {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      logger.warn(`API PUT failed: ${endpoint}`, {
        extra: { status: response.status, statusText: response.statusText },
      });
      throw new Error(`API error: ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    logger.error(`API PUT error: ${endpoint}`, { error });
    throw error;
  }
}

/**
 * Make a DELETE request to the API.
 */
export async function del(endpoint) {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      logger.warn(`API DELETE failed: ${endpoint}`, {
        extra: { status: response.status, statusText: response.statusText },
      });
      throw new Error(`API error: ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    logger.error(`API DELETE error: ${endpoint}`, { error });
    throw error;
  }
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
    send: (data) => post('/chat/', data),
  },
};
