import { proxyToRender } from '../proxy.js';

export const config = { api: { bodyParser: false } };
export default function handler(request, response) {
  return proxyToRender(request, response, 'api');
}
