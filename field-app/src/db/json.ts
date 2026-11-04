/** JSON in and out of TEXT columns, in one place. */
export function toJson(value: unknown): string | null {
  return value === undefined || value === null ? null : JSON.stringify(value);
}

export function fromJson<T = unknown>(text: string | null | undefined): T | null {
  if (text === null || text === undefined || text === '') return null;
  return JSON.parse(text) as T;
}
