# AstroBirthChart — optional local Dicta 1.7 via llama-server (N2 prose)

## Intent and non-goals

This is an optional **wording-only** adapter downstream of N2. It does **not**
change the chart calculator, N1, R1, N2 claims/evidence/meanings or any N3
contracts. N2's original deterministic narrative remains visible, copyable,
and authoritative; the model-written result is explicitly marked **unverified**.

This feature is **off by default**. Opening the interpretation window does not
make any model connection.

## Start the local server (Windows)

If you already run Dicta 1.7 with llama-server, leave that server running.
The application uses port 8080 by default. A command **example** when starting
the server yourself (substitute the actual installed executable and model
GGUF file path):

    llama-server -m "C:\path\to\your-dicta-model.gguf" --host 127.0.0.1 --port 8080 -c 8192

The available conversation context and compatible chat template depend on
the actual model and server setup; the example is not a universal prescription.

Verify locally (in a browser or PowerShell):

    http://127.0.0.1:8080/v1/models

The application discovers the model ID from this endpoint, then calls only
POST /v1/chat/completions. It does not download or install the model.

## Use

1. Calculate a chart and open **פרשנות אופי (ניסוי)**.
2. The ordinary **פרשנות אישית (N2)** remains unchanged.
3. Open **ניסוח Dicta מקומי** or press **נסח עם Dicta המקומי**.
4. If llama-server uses a different port, select it in the numeric field.
5. Read the confirmation: only the structured *semantic passages* from
   the current N2 narrative go to the chosen **local** server.
6. Approve explicitly for each generation. Processing runs in a worker
   thread, keeping the UI responsive. A timeout or invalid response shows
   the original N2 text, never a claimed AI success.

Copy the model wording only when the model returns a valid text result.

## Privacy and boundaries

- Address is hard-coded to **127.0.0.1**. Port must be 1–65535.
- No remote URL configuration, DNS host, proxy, redirects, streaming,
  token, account or cloud dependency; outbound traffic is not expected.
- Birth date, birth location, raw body positions and the original
  evidence/source URLs are **not sent by this feature**. Only N2-selected
  semantic paragraphs, their editorial classifications/audit statuses
  and the time-certainty mode are included.
- The user is responsible for trusting the process actually listening on
  localhost and any data handling performed by that process.
- Responses have strict size limits; invalid JSON, missing model, empty
  output or truncated answers fail closed, leaving N2 unchanged.
- Generation may not reliably follow every instruction: the system prompt
  asks for source-faithful wording and preservation of uncertainty, but
  **there is no semantic proof that the model's output added no new claim**.
  The model tab clearly labels the result as unverified; users must compare
  with N2 and its proof tabs. Never treat the AI output as an approved
  N2 claim or verified astrological fact.
- Not a scientific personality assessment and no predictive validity claim.

## Tests and release gate

Run:

    python -m pytest -q tests/test_local_llm.py
    python -m pytest -q

The unit tests use fakes, never a real network model. UI tests confirm that
opening the dialog and rejecting consent never contact the model.
A manual Windows integration check with a running local llama-server and
a real Dicta model remains required before release. This feature must not
be merged or shipped based solely on unit-test success.
