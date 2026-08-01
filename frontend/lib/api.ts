import type { CombinedModule3Payload, Module1Result, Module2Result } from "./types";

const MODULE1_BASE_URL = process.env.NEXT_PUBLIC_MODULE1_BASE_URL ?? "http://127.0.0.1:5000";
const MODULE2_BASE_URL = process.env.NEXT_PUBLIC_MODULE2_BASE_URL ?? "http://127.0.0.1:8010";
const MODULE2_API_KEY = process.env.NEXT_PUBLIC_MODULE2_API_KEY ?? "";

export type EssayInput = { text: string } | { file: File };

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.error ?? body.detail ?? `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

/** Module 1's /score — internally also calls Module 2 server-side, so this
 * one call already returns the combined D1-D4 result. See module_1/app.py. */
export async function callModule1(input: EssayInput, essayId: string): Promise<Module1Result> {
  let response: Response;
  if ("file" in input) {
    const form = new FormData();
    form.append("essay_file", input.file);
    form.append("essay_id", essayId);
    response = await fetch(`${MODULE1_BASE_URL}/score`, { method: "POST", body: form });
  } else {
    response = await fetch(`${MODULE1_BASE_URL}/score`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ essay: input.text, essay_id: essayId }),
    });
  }
  if (!response.ok) {
    throw new Error(`Module 1: ${await readErrorMessage(response)}`);
  }
  return response.json();
}

/** Direct browser -> Module 2 call, in parallel with Module 1, purely so
 * the Module 2 panel can render as soon as it's ready rather than waiting
 * for Module 1's own (server-side) call to Module 2 to finish. */
export async function callModule2(input: EssayInput, submittedBy: string): Promise<Module2Result> {
  let response: Response;
  if ("file" in input) {
    const form = new FormData();
    form.append("file", input.file);
    form.append("submitted_by", submittedBy);
    response = await fetch(`${MODULE2_BASE_URL}/api/v1/essay/check-file`, {
      method: "POST",
      headers: { "X-API-Key": MODULE2_API_KEY },
      body: form,
    });
  } else {
    response = await fetch(`${MODULE2_BASE_URL}/api/v1/essay/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": MODULE2_API_KEY },
      body: JSON.stringify({ essay_text: input.text, submitted_by: submittedBy }),
    });
  }
  if (!response.ok) {
    throw new Error(`Module 2: ${await readErrorMessage(response)}`);
  }
  return response.json();
}

/** Module 1's /score-offline — for when Module 2 ISN'T running on this
 * machine. Instead of Module 1 calling Module 2 itself, you supply a
 * Module 2 result JSON you already have (e.g. downloaded from the
 * standalone Module 2 page earlier, while Module 2 WAS running). Module 1
 * still scores D2-D4 itself and merges everything into the identical
 * combined output /score produces. See module_1/app.py's /score-offline. */
export async function callModule1Offline(
  input: EssayInput,
  module2Json: File,
  essayId: string,
): Promise<Module1Result> {
  const form = new FormData();
  if ("file" in input) {
    form.append("essay_file", input.file);
  } else {
    form.append("essay_text", input.text);
  }
  form.append("module2_file", module2Json);
  form.append("essay_id", essayId);

  const response = await fetch(`${MODULE1_BASE_URL}/score-offline`, { method: "POST", body: form });
  if (!response.ok) {
    throw new Error(`Module 1: ${await readErrorMessage(response)}`);
  }
  return response.json();
}

/** Fetches the final combined Module-3 payload Module 1 already built and
 * saved during its /score call (see module_1/app.py's
 * GET /api/v1/module3/<essay_id>) — reads it back rather than
 * reconstructing the D2/D3/D4 renaming logic in TypeScript, so this can
 * never drift from what Module 1 actually wrote to disk for Module 3. */
export async function fetchCombinedPayload(apiUrl: string): Promise<CombinedModule3Payload> {
  const response = await fetch(apiUrl);
  if (!response.ok) {
    throw new Error(`Combined output: ${await readErrorMessage(response)}`);
  }
  return response.json();
}