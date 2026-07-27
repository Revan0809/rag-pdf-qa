import type { AskResponse, UploadResponse } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_BASE_URL) {
  // Fails loudly at build/runtime rather than silently calling the wrong host.
  console.warn(
    "NEXT_PUBLIC_API_URL is not set. API calls will fail. See frontend/.env.example."
  );
}

/**
 * Reads a JSON error body from a failed response, falling back to the
 * status text if the body isn't valid JSON (e.g. an unrelated 502 from a
 * platform edge, not our FastAPI app).
 */
async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.detail ?? response.statusText;
  } catch {
    return response.statusText || `Request failed with status ${response.status}`;
  }
}

/**
 * Uploads a PDF via XMLHttpRequest (rather than fetch) so we can report
 * upload progress as bytes are sent to the server.
 */
export function uploadPdf(
  file: File,
  onUploadProgress: (percent: number) => void
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        onUploadProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      let body: Record<string, unknown> = {};
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // handled below via status check
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as unknown as UploadResponse);
      } else {
        reject(
          new Error((body.detail as string) || `Upload failed with status ${xhr.status}`)
        );
      }
    });

    xhr.addEventListener("error", () => reject(new Error("Network error during upload.")));

    xhr.open("POST", `${API_BASE_URL}/upload`);
    xhr.send(formData);
  });
}

export async function askQuestion(documentId: string, question: string): Promise<AskResponse> {
  const response = await fetch(`${API_BASE_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: documentId, question }),
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json();
}
