import { revalidatePath } from 'next/cache';

export const dynamic = 'force-dynamic';

export async function POST() {
  revalidatePath('/');
  return Response.json({ revalidated: true, timestamp: new Date().toISOString() });
}
