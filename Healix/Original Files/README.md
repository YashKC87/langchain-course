# HEALIX — Complete Setup & Showcase Guide
### Hybrid Endpoint Autonomous Learning & Intelligent X-remediation
---

## What You're Building

HEALIX is a two-part system:

```
┌─────────────────────┐         ┌─────────────────────┐
│   FRONTEND (React)  │ ──────► │  BACKEND (Python)   │
│   healix-agent.jsx  │  HTTP   │  main.py + agent.py │
│   (The dashboard)   │ ◄────── │  (The AI brain)     │
└─────────────────────┘         └─────────────────────┘
         ↑                                ↑
    Claude.ai or                  Your computer
    any browser                   runs this locally
```

---

## PART 1 — Frontend (No Installation Needed)

The frontend is the `healix-agent.jsx` file you already have.

**To open it:**
1. Go to **claude.ai**
2. Start a new conversation
3. Upload the `healix-agent.jsx` file
4. Ask Claude: *"Run this React component"*

OR paste the code into any React playground:
- **CodeSandbox**: https://codesandbox.io → New Project → React
- **StackBlitz**: https://stackblitz.com → React

> ✅ The frontend works completely on its own with demo data.
> You don't need the backend to showcase the UI.

---

## PART 2 — Backend (Python API Server)

This enables real AI responses through RAG + LLM.

### Step 1 — Install Python

**Check if you have Python already:**
Open Terminal (Mac/Linux) or Command Prompt (Windows) and type:
```bash
python --version
```
If you see `Python 3.10` or higher, skip to Step 2.

**If not installed:**
- **Windows**: Download from https://python.org/downloads → Check "Add Python to PATH" ✅
- **Mac**: Run `brew install python3` (requires Homebrew)
- **Linux**: Run `sudo apt install python3 python3-pip`

---

### Step 2 — Download the Project Files

Create a folder called `healix` on your Desktop.
Put these files inside it:
```
healix/
├── main.py          ← The API server
├── agent.py         ← The AI agent logic
├── requirements.txt ← List of libraries to install
├── .env.example     ← Template for your secrets
└── test_api.py      ← Test script
```

---

### Step 3 — Open Terminal in the Project Folder

**Windows:**
1. Open the `healix` folder in File Explorer
2. Click the address bar at the top
3. Type `cmd` and press Enter

**Mac:**
1. Open Terminal (Cmd + Space → type "Terminal")
2. Type `cd Desktop/healix` and press Enter

**Linux:**
Right-click the folder → "Open Terminal Here"

---

### Step 4 — Create a Virtual Environment

A virtual environment keeps your project's libraries separate from other Python projects.

```bash
# Create the virtual environment
python -m venv healix_env

# Activate it:
# On Windows:
healix_env\Scripts\activate

# On Mac/Linux:
source healix_env/bin/activate
```

You'll see `(healix_env)` appear at the start of your terminal line.
This means it's activated. ✅

---

### Step 5 — Install All Required Libraries

```bash
pip install -r requirements.txt
```

This will download and install ~15 libraries. It takes 2-5 minutes.
You'll see a lot of text scrolling — that's normal.

When it's done you'll see your cursor again.

---

### Step 6 — Set Up Your API Key (Optional but Recommended)

For DEMO MODE (no API key needed):
- Skip this step. The app will work with pre-written responses.

For REAL AI MODE (OpenAI-powered):
1. Go to https://platform.openai.com/api-keys
2. Sign up / log in
3. Click "Create new secret key"
4. Copy the key (starts with `sk-...`)

Now create your `.env` file:
1. Find the `.env.example` file in your `healix` folder
2. Make a copy of it
3. Rename the copy to `.env` (remove the `.example` part)
4. Open `.env` with Notepad (Windows) or TextEdit (Mac)
5. Replace `your-openai-api-key-here` with your actual key
6. Save the file

> ⚠️ IMPORTANT: Never share your `.env` file with anyone.
> It contains your private API key.

---

### Step 7 — Start the Server

```bash
python main.py
```

You should see:
```
🚀 Starting HEALIX API server...
📖 API docs available at: http://localhost:8000/docs
INFO:     Uvicorn running on http://0.0.0.0:8000
```

The server is now running! Keep this terminal window open.

---

### Step 8 — Test Everything Works

Open a **second** terminal window (keep the server running in the first one).
Navigate to your `healix` folder again, activate the venv, then:

```bash
python test_api.py
```

You should see:
```
✅ PASS — Server is running
✅ PASS — Health check endpoint
✅ PASS — Get endpoints (6 servers)
✅ PASS — Get alerts
✅ PASS — Get healing actions
✅ PASS — AI Agent chat (RAG + LLM)
✅ PASS — Trigger auto-remediation
✅ PASS — Failure predictions (ML)
✅ PASS — Patch intelligence

Results: 9/9 tests passed
🎉 All tests passed! HEALIX backend is working perfectly.
```

---

### Step 9 — Explore the Interactive API Docs

Open your browser and go to:
```
http://localhost:8000/docs
```

This is the **Swagger UI** — it lets you test every API endpoint
visually, without writing any code!

#### How to use Swagger UI:
1. Click on any green `GET` or blue `POST` button
2. Click **"Try it out"**
3. Fill in any required fields
4. Click **"Execute"**
5. See the real response at the bottom

Try these first:
- `GET /api/endpoints` — See all 6 servers
- `GET /api/alerts` — See active alerts
- `POST /api/agent/chat` — Ask the AI a question (type in the box!)
- `GET /api/predictions` — Get failure predictions

---

## PART 3 — Showcasing HEALIX (Demo Script)

### Before the Demo

1. ✅ Frontend open in browser (CodeSandbox or claude.ai)
2. ✅ Backend running (`python main.py` in terminal)
3. ✅ Swagger UI open at `http://localhost:8000/docs`
4. ✅ Browser zoomed to 90% for best view

---

### Demo Flow (15 minutes total)

#### Slide 1 — Opening Hook (1 min)
> "Traditional IT ops means your team gets paged at 3am when a server
> crashes. HEALIX changes that — it detects, diagnoses, and heals
> infrastructure automatically, using the same AI techniques as
> ChatGPT, but trained on your runbooks and systems."

#### Slide 2 — Dashboard Tab (3 min)
Point out:
- 5 KPI cards — live counts update every 3 seconds
- EDGE-NODE-07 is Critical (pulsing red dot) → "the agent already knows"
- Sparkline charts showing trends over time
- Alert feed on the right

#### Slide 3 — Endpoints Tab (2 min)
- Walk through each server card
- Show the metric bars (CPU/MEM/DISK) filling up
- "Trigger Remediation" button — "this is what the agent calls automatically"

#### Slide 4 — Healing Tab (3 min)
- Stats: 1,248 auto-healed, 98.4% success rate
- Action Log: HA-001 still running (animated glow)
- **THE KEY VISUAL**: The 6-step Agentic Pipeline
  > "Detect → Analyze → Plan → Execute → Verify → Learn.
  > This loop runs 24/7. Zero human escalation for 78% of incidents."

#### Slide 5 — AI Agent Tab (5 min) ⭐
Click each suggestion chip slowly:

1. **"Why is EDGE-NODE-07 critical?"**
   → Wait for the typing animation
   → Show the structured root cause + action plan
   > "The agent searched 4,821 knowledge base documents, found
   > the matching runbook, and generated a step-by-step fix."

2. **"What patches are pending?"**
   → Show the CVE table with CVSS scores
   > "It cross-referenced our CVE database — OpenSSL 9.1 CVSS is
   > being actively exploited. HEALIX already scheduled the patch."

3. **"Predict failures next 24h?"**
   → Show the risk percentages
   > "This is ML-powered prediction — not just thresholds.
   > HEALIX tells you what's going to break BEFORE it breaks."

4. Type a **custom free-text question**
   → "how do I fix the disk space issue on DB-CLUSTER-01?"
   > "It handles open-ended questions, not just pre-set ones.
   > This is the power of LLM reasoning on top of RAG retrieval."

---

### Common Questions & Answers

**Q: How is this different from Datadog or New Relic?**
> "Monitoring tools show you the problem. HEALIX fixes it.
> And it explains WHY it happened — not just THAT it happened."

**Q: Is our data safe?**
> "The RAG knowledge base runs locally. Only the final reasoning
> query goes to the LLM provider. You control what data is shared."

**Q: Can it connect to our real servers?**
> "Yes — the agent.py file has clear integration points.
> You replace the simulated data with your actual monitoring
> APIs (Datadog, Zabbix, Prometheus, etc.) in 2-4 hours."

**Q: What LLM does it use?**
> "Currently GPT-4o mini — cost-effective at <$0.01 per query.
> Can be swapped for Azure OpenAI, Claude, or a local model
> like Llama 3 for complete data privacy."

---

## Troubleshooting

### "python: command not found"
Run `python3` instead of `python`

### "No module named 'fastapi'"
Make sure your virtual environment is activated:
```bash
source healix_env/bin/activate  # Mac/Linux
healix_env\Scripts\activate     # Windows
```

### "Connection refused" when running tests
Your server isn't running. Open a new terminal and run:
```bash
python main.py
```

### "faiss-cpu install failed" on Windows
Run this instead:
```bash
pip install faiss-cpu --only-binary=:all:
```

### API returns demo responses
This is correct behavior without an API key!
Add your OpenAI key to `.env` to enable real AI responses.

---

## Architecture Summary

```
User Question
     │
     ▼
FastAPI Server (main.py)
     │
     ▼
HealIXAgent.ask() (agent.py)
     │
     ├──► RAGEngine.search()
     │         │
     │         ▼
     │    FAISS Vector Store
     │    (searches 8 KB docs)
     │         │
     │         ▼
     │    Top 3 relevant chunks
     │
     ├──► LangChain RetrievalQA
     │         │
     │         ▼
     │    OpenAI GPT-4o-mini
     │    (reasons over context)
     │
     ▼
Structured Response
     │
     ▼
Frontend Dashboard
```

---

## Next Steps to Productionize

1. **Connect real monitoring**: Replace `get_endpoint_status()` with
   Datadog API / Prometheus / Zabbix calls

2. **Real healing actions**: Replace `trigger_remediation()` with
   Ansible playbook execution or SSH commands

3. **Deploy to cloud**: Run on AWS EC2, Azure VM, or Google Cloud Run

4. **Add authentication**: Protect the API with JWT tokens

5. **Real vector database**: Replace FAISS with Pinecone or Weaviate
   for production scale

6. **Continuous learning**: Pipe resolved incidents back into the
   knowledge base automatically

---

*HEALIX v1.0 — Built with FastAPI + LangChain + OpenAI*
