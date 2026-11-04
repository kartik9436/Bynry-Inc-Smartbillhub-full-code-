/**
 * `customer` — name, account number, contact. No balance and no tariff: those
 * are online-only (Mobile data §2) and money is read-only in this app (R16).
 * Not scoped (R132).
 */
import type { TenantDb } from '../database';
import { toJson } from '../json';

export interface CustomerRow {
  id: string;
  name: string | null;
  account_number: string | null;
  phone: string | null;
  email: string | null;
  extra: string | null;
  updated_at: string;
}

export interface CustomerInput {
  id: string;
  name?: string | null;
  accountNumber?: string | null;
  phone?: string | null;
  email?: string | null;
  extra?: Record<string, unknown> | null;
}

export function upsert(db: TenantDb, c: CustomerInput, now: string): void {
  db.ref.run(
    `INSERT INTO customer (id, name, account_number, phone, email, extra, updated_at)
     VALUES (:id, :name, :account_number, :phone, :email, :extra, :now)
     ON CONFLICT (id) DO UPDATE SET
       name = excluded.name, account_number = excluded.account_number, phone = excluded.phone,
       email = excluded.email, extra = excluded.extra, updated_at = excluded.updated_at`,
    {
      id: c.id,
      name: c.name,
      account_number: c.accountNumber,
      phone: c.phone,
      email: c.email,
      extra: toJson(c.extra),
      now,
    },
  );
}

export function get(db: TenantDb, id: string): CustomerRow | undefined {
  return db.ref.get<CustomerRow>('SELECT * FROM customer WHERE id = :id', { id });
}
