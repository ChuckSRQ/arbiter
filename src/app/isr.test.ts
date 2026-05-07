import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

test("page exports ISR revalidation for the dashboard", () => {
  const pageSource = readFileSync(resolve(process.cwd(), "src", "app", "page.tsx"), "utf8");

  assert.match(pageSource, /export const revalidate = 60;/);
});

test("revalidate API route exists with the expected cache-busting handler", () => {
  const routePath = resolve(process.cwd(), "src", "app", "api", "revalidate", "route.ts");

  assert.equal(existsSync(routePath), true, "route.ts should exist");

  const routeSource = readFileSync(routePath, "utf8");

  assert.match(routeSource, /import \{ revalidatePath \} from 'next\/cache';/);
  assert.match(routeSource, /export const dynamic = 'force-dynamic';/);
  assert.match(routeSource, /export async function POST\(\) \{/);
  assert.match(routeSource, /revalidatePath\('\/'\);/);
  assert.match(
    routeSource,
    /return Response\.json\(\{ revalidated: true, timestamp: new Date\(\)\.toISOString\(\) \}\);/,
  );
});
