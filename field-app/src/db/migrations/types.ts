/** One forward-only migration. There is no `down`, on purpose. */
export interface Migration {
  /** 1, 2, 3 … with no gaps, never reused. */
  readonly id: number;
  readonly name: string;
  readonly statements: readonly string[];
}
