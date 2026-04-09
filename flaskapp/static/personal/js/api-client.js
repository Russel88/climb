export async function apiGet(url) {
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  return handleResponse(response);
}

export async function apiPost(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload ?? {}),
  });
  return handleResponse(response);
}

export async function apiPut(url, payload) {
  const response = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload ?? {}),
  });
  return handleResponse(response);
}

export async function apiDelete(url) {
  const response = await fetch(url, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  });
  return handleResponse(response);
}

async function handleResponse(response) {
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const message = payload?.error || `Request failed (${response.status})`;
    throw new Error(message);
  }

  return payload;
}

export function setToast(target, message, isError = false) {
  if (!target) {
    return;
  }

  target.textContent = message;
  target.classList.add('toast');
  target.classList.toggle('error', isError);
}
