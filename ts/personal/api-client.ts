export async function apiGet<T = unknown>(url: string): Promise<T> {
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  return handleResponse<T>(response);
}

export async function apiPost<T = unknown>(url: string, payload: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload ?? {}),
  });
  return handleResponse<T>(response);
}

export async function apiPut<T = unknown>(url: string, payload: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload ?? {}),
  });
  return handleResponse<T>(response);
}

export async function apiDelete<T = unknown>(url: string): Promise<T> {
  const response = await fetch(url, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  });
  return handleResponse<T>(response);
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

async function handleResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  const payload: unknown = text ? JSON.parse(text) : {};

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    if (payload && typeof payload === 'object' && 'error' in payload) {
      const errorValue = (payload as { error?: unknown }).error;
      if (typeof errorValue === 'string' && errorValue) {
        message = errorValue;
      }
    }
    throw new Error(message);
  }

  return payload as T;
}

export function setToast(target: HTMLElement | null, message: string, isError = false): void {
  if (!target) {
    return;
  }

  target.textContent = message;
  target.classList.add('toast');
  target.classList.toggle('error', isError);
}
