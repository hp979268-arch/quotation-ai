import { readString, removeValue, writeString } from './utils/storage';

export const API_OVERRIDE_KEY = 'quotation-ai/api-base-url';
// Use the current IP/Hostname where the frontend is loaded, so it works seamlessly on mobile over Wi-Fi
export const DEFAULT_API_BASE = 'https://quotation-ai-backend-dn5t.onrender.com';

const normalizeBase = (value) => String(value || '').trim().replace(/\/+$/, '');

export function getApiBase() {
  const isElectron =
    typeof window !== 'undefined' &&
    (window.location.protocol === 'file:' ||
      (window.navigator && window.navigator.userAgent && window.navigator.userAgent.includes('Electron')) ||
      Boolean(window.desktopApp && window.desktopApp.isDesktop));

  const fromStorage = normalizeBase(readString(API_OVERRIDE_KEY, ''));

  if (isElectron) {
    // In desktop software, only use storage override if it is a local URL, otherwise default to local sidecar
    if (fromStorage && (fromStorage.includes('127.0.0.1') || fromStorage.includes('localhost'))) {
      return fromStorage;
    }
    return 'http://127.0.0.1:8000';
  }

  if (fromStorage) return fromStorage;

  const fromEnv = normalizeBase(process.env.REACT_APP_API_URL || '');
  return fromEnv || DEFAULT_API_BASE;
}

// For quote history (list, get, delete): always use Render cloud so history is never lost
export function getHistoryBase() {
  return DEFAULT_API_BASE;
}


export function hasApiBaseOverride() {
  return Boolean(normalizeBase(readString(API_OVERRIDE_KEY, '')));
}

export function setApiBaseOverride(nextBase) {
  const normalized = normalizeBase(nextBase);
  if (!normalized) {
    removeValue(API_OVERRIDE_KEY);
    return '';
  }
  writeString(API_OVERRIDE_KEY, normalized);
  return normalized;
}

export function clearApiBaseOverride() {
  removeValue(API_OVERRIDE_KEY);
}

const BASE = getApiBase();

export default BASE;

