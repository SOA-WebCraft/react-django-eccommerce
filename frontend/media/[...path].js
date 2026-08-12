import { proxyToBackend } from '../proxy.js';

export const config = { api: { bodyParser: false } };
export default function handler(request, response) {
  return proxyToBackend(request, response, 'media');
}
