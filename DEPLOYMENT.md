# Deployment Guide — Vercel (frontend) + Railway (backend)

You'll deploy in this order:

1. **Railway** — deploy backend, get its URL
2. **Vercel** — deploy frontend, point it at the Railway URL
3. **Railway** — update CORS to allow the Vercel URL, redeploy

Cost: free tier on Vercel + ~$5/mo Hobby tier on Railway (covered by Railway's $5/mo free credit on light usage). MongoDB Atlas M0 + Groq free tier stay free.

---

## Prerequisites

- GitHub repo with this code (you have it: `I221165/RAG-DD`)
- `GROQ_API_KEY` and `MONGODB_URI` from earlier
- MongoDB Atlas IP allowlist set to `0.0.0.0/0` (Railway uses dynamic IPs)

---

## Step 1 — Deploy backend to Railway

1. Go to https://railway.app, sign in with GitHub.
2. **New Project** → **Deploy from GitHub repo** → select **`I221165/RAG-DD`**.
3. Railway will start building. Once it appears as a service, open it.
4. **Settings → Service → Source**:
   - **Root Directory:** `backend`
   - Railway auto-detects the `Dockerfile` and uses it.
5. **Variables** tab — add:
   ```
   GROQ_API_KEY        = <your key>
   MONGODB_URI         = <your atlas connection string>
   MONGODB_DB_NAME     = rag_chatbot
   ALLOWED_ORIGINS     = ["http://localhost:5173"]
   ```
   (We'll update `ALLOWED_ORIGINS` with the Vercel URL in Step 3.)
6. **Settings → Volumes** → **New Volume**:
   - **Mount path:** `/app/chroma_db`
   - **Size:** 1 GB (Hobby tier default)
   - This makes Chroma data survive container restarts. Without it, every redeploy wipes your embeddings.
7. (Optional) Add a second volume mounted at `/app/uploads` if you want the raw uploaded files to persist too. Not strictly needed — the embeddings are what matters for retrieval.
8. **Settings → Networking** → **Generate Domain**. Copy the URL — looks like:
   ```
   https://rag-dd-production.up.railway.app
   ```
9. Wait for the build to finish (first build is ~5-8 min — torch is large). Visit `https://<your-railway-url>/health` to verify:
   ```json
   { "status": "ok", "mongodb": "connected", "vector_store": "ready", "llm": "configured" }
   ```

---

## Step 2 — Deploy frontend to Vercel

1. Go to https://vercel.com, sign in with GitHub.
2. **Add New** → **Project** → select **`I221165/RAG-DD`**.
3. Configure:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Vite (auto-detected)
   - Build / output settings: leave defaults (`npm run build` → `dist`)
4. **Environment Variables** — add:
   ```
   VITE_API_BASE = https://rag-dd-production.up.railway.app
   ```
   (Use your actual Railway URL from Step 1.8. No trailing slash.)
5. **Deploy**. After ~1-2 minutes you'll get a URL like:
   ```
   https://rag-dd.vercel.app
   ```
6. Open it — the sidebar will appear but uploads/chat will fail (CORS, because we haven't whitelisted Vercel yet). That's expected.

---

## Step 3 — Wire CORS so the frontend can talk to the backend

1. Back to Railway → your backend service → **Variables**.
2. Update `ALLOWED_ORIGINS` to include your Vercel URL:
   ```
   ALLOWED_ORIGINS = ["https://rag-dd.vercel.app"]
   ```
   (You can include multiple: `["https://rag-dd.vercel.app", "http://localhost:5173"]`)
3. Railway auto-redeploys on env change. Wait for "Deployment live".
4. Refresh the Vercel app. Upload, chat, follow-up — everything should work.

---

## Verifying

- Visit `https://<your-railway-url>/health` — all green.
- Open Vercel app, upload a doc, ask a question. Expected: streaming token-by-token response. Sources show below.
- DevTools → Network → `/chat` request should be cross-origin to your Railway domain with status 200 and `application/x-ndjson` content type.

---

## Troubleshooting

**"ECONNREFUSED" or "Failed to fetch" in the frontend**
→ Railway service is sleeping or down. Visit `<railway-url>/health` in a new tab to wake it / confirm. Hobby tier always-on, free tier sleeps after inactivity.

**"CORS error" in browser console**
→ `ALLOWED_ORIGINS` on Railway doesn't include your exact Vercel URL (including `https://`). Update and wait for redeploy.

**"GROQ_API_KEY not set" at startup**
→ Variable name typo, or you set it in the wrong service. Check Railway → Variables.

**Chroma data disappears between deploys**
→ Volume wasn't mounted at `/app/chroma_db`. Re-check Railway → Settings → Volumes.

**Cold start takes 30+ seconds**
→ First request after idle has to load the embedder model. Expected on free/hobby tiers. Subsequent requests are fast.

**Upload works locally but fails on Vercel**
→ Check the request URL in DevTools. If it's hitting `https://rag-dd.vercel.app/upload` (your Vercel URL), `VITE_API_BASE` wasn't set during build. Redeploy Vercel after setting the env var — Vite bakes env vars in at build time.

**Streaming works locally but not on Vercel**
→ Some proxies strip / buffer streams. Both Vercel (for static) and Railway (for the backend) handle streaming fine by default, but if you put another CDN in front, set `proxy_buffering off` / equivalent.

---

## Updating after the first deploy

- Push to `main` → both Vercel and Railway auto-rebuild and redeploy.
- Code changes that affect env vars (e.g., new required setting) need the variable added in the platform UI.
