import { Page, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import path from 'path';

export type Fixtures = {
  runId: string;
  supabaseUrl: string;
  serviceRoleKey: string;
  customer: { id: string; email: string; password: string };
  admin: { id: string; email: string; password: string };
};

export function loadFixtures(): Fixtures {
  return JSON.parse(readFileSync(path.join(__dirname, '.auth', 'fixtures.json'), 'utf-8'));
}

/** Real UI login: fills the form and waits for the post-login redirect. */
export async function loginViaUi(page: Page, email: string, password: string, expectedPath: RegExp) {
  await page.goto('/login');
  await page.getByPlaceholder('Email address').fill(email);
  await page.getByPlaceholder('Password').fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await expect(page).toHaveURL(expectedPath, { timeout: 20_000 });
}
