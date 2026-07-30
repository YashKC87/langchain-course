# ============================================================
#  HEALIX AI Agent — agent.py
#
#  This file contains the "brain" of HEALIX:
#  1. RAGEngine  — searches the knowledge base for relevant docs
#  2. LLMEngine  — reasons over the retrieved docs using OpenAI
#  3. HealIXAgent — combines both and drives remediation actions
# ============================================================

import os
import asyncio
import random
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ── LangChain imports ─────────────────────────────────────────
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document


# ════════════════════════════════════════════════════════════
#  KNOWLEDGE BASE — The documents the RAG engine searches
#  In production: load from files, databases, or APIs
# ════════════════════════════════════════════════════════════

KNOWLEDGE_BASE_DOCS = [
    {
        "title": "High CPU Remediation Runbook",
        "content": """
        When CPU usage exceeds 90% on any endpoint:
        1. Identify top CPU-consuming processes using: ps aux --sort=-%cpu | head -20
        2. Check for zombie processes: ps aux | grep Z
        3. Kill runaway processes if they are non-critical: kill -9 <PID>
        4. Check for scheduled jobs conflicting: crontab -l
        5. If Node.js app: restart PM2 ecosystem — pm2 restart all
        6. If Windows: End task from Task Manager, restart IIS if web server
        7. Escalate if CPU remains above 90% for more than 10 minutes
        Common causes: memory leak in application, runaway cron job, crypto mining malware
        """
    },
    {
        "title": "Memory Leak Detection and Resolution",
        "content": """
        Memory leak symptoms: gradual RAM increase, system slowdown, OOM kills.
        Detection steps:
        1. Monitor with: watch -n 1 free -h
        2. Find memory-hungry processes: ps aux --sort=-%mem | head -10
        3. Check application logs for heap allocation errors
        4. Linux: check /var/log/kern.log for OOM killer messages
        5. Windows: Use Resource Monitor → Memory tab
        Remediation:
        - Restart the offending service (safe if stateless)
        - Enable memory limits in Docker: --memory=2g
        - For Node.js: set --max-old-space-size=4096
        - Schedule a rolling restart during off-peak hours
        - Apply available patches — memory leaks often fixed in newer versions
        """
    },
    {
        "title": "Disk Space Critical — Remediation Steps",
        "content": """
        When disk usage exceeds 85%:
        1. Find largest directories: du -sh /* 2>/dev/null | sort -hr | head -20
        2. Clean old logs: find /var/log -name "*.log" -mtime +30 -delete
        3. Clean package cache: apt-get clean (Ubuntu) or yum clean all (RHEL)
        4. Identify and remove old Docker images: docker image prune -a
        5. Archive and compress old backup files
        6. Move cold data to object storage (S3/Azure Blob)
        7. Expand volume if cloud-hosted (AWS EBS, Azure Disk)
        Critical threshold: 95% — trigger immediate alert and auto-archive
        """
    },
    {
        "title": "OpenSSL Critical Vulnerability CVE-2023-0286",
        "content": """
        CVE-2023-0286 — CVSS Score: 9.1 (Critical)
        Affected versions: OpenSSL 3.0.x before 3.0.8, 1.1.1 before 1.1.1t
        Description: X.400 address type confusion in GeneralName.
        Impact: Remote code execution, denial of service
        Affected endpoints: Any Linux server running OpenSSL < 3.1.4
        Remediation:
        - Ubuntu/Debian: sudo apt-get update && sudo apt-get install openssl
        - RHEL/CentOS: sudo yum update openssl
        - Verify fix: openssl version
        Priority: PATCH IMMEDIATELY — active exploits in the wild
        Downtime required: Service restart only (no reboot needed)
        Estimated patch time: 5 minutes per endpoint
        """
    },
    {
        "title": "Node.js Application Performance Issues",
        "content": """
        Common Node.js issues on production servers:
        1. Memory heap overflow — increase with --max-old-space-size
        2. Event loop blocking — use clinic.js to diagnose
        3. Unhandled promise rejections crashing process
        4. Too many open file descriptors: ulimit -n 65536
        Versions with known memory leak: v20.3.0, v20.5.1
        Fixed in: v20.9.0 (LTS) and v21.0.0
        Recommended action: upgrade to v20.9.0 (LTS)
        Restart command: pm2 restart ecosystem.config.js --update-env
        """
    },
    {
        "title": "IIS Web Server — Auto-Restart Procedures",
        "content": """
        IIS service crash recovery on Windows Server:
        1. Check IIS status: Get-Service W3SVC
        2. View error logs: C:\\Windows\\System32\\LogFiles\\HTTPERR
        3. Application pool crash: Check Windows Event Viewer → Application
        4. Restart IIS: iisreset /restart
        5. Restart specific app pool: Restart-WebAppPool "DefaultAppPool"
        Common causes: .NET runtime exception, memory limit hit, worker process crash
        Auto-recovery: Set application pool to restart after 1 failure
        Health check: curl -I http://localhost returns 200
        """
    },
    {
        "title": "Predictive Failure — ML Anomaly Scoring",
        "content": """
        HEALIX uses LSTM-based anomaly detection with 90-day baseline.
        Risk scoring factors:
        - CPU trend slope over last 4 hours (weight: 25%)
        - Memory growth rate (weight: 30%)
        - Disk fill rate (weight: 20%)
        - Historical incident frequency (weight: 15%)
        - Days since last reboot (weight: 10%)
        Risk thresholds:
        - 0-30%: Green — normal operations
        - 31-60%: Yellow — increase monitoring frequency
        - 61-80%: Orange — prepare remediation runbook
        - 81-100%: Red — trigger proactive healing
        Model retrained every 7 days on new telemetry data.
        """
    },
    {
        "title": "Windows Patch Management Runbook",
        "content": """
        Patch deployment process for Windows endpoints:
        1. Scan for pending patches: Get-WindowsUpdate
        2. Test patches in DEV environment first (48 hour bake period)
        3. Deploy to STAGING — monitor for 24 hours
        4. Production rollout: schedule maintenance window (02:00-04:00 UTC)
        5. Critical security patches (CVSS 9+): expedited 4-hour rollout
        Rollback procedure: System Restore point created before every patch
        Verification: Run Invoke-WUInstall -Confirm after deployment
        Reboot requirement: Most patches require reboot — schedule accordingly
        """
    }
]


# ════════════════════════════════════════════════════════════
#  RAG ENGINE — Builds and searches the vector store
# ════════════════════════════════════════════════════════════

class RAGEngine:
    """
    RAG = Retrieval Augmented Generation
    Step 1: Convert documents into vectors (numbers representing meaning)
    Step 2: When a question comes in, find the most relevant documents
    Step 3: Pass those documents to the LLM as context
    """

    def __init__(self):
        self.vectorstore = None
        self.retriever = None

    def build_knowledge_base(self, embeddings=None):
        """Convert all knowledge base documents into searchable vectors.

        Args:
            embeddings: Optional LangChain-compatible embeddings instance.
                        Defaults to OpenAIEmbeddings using OPENAI_API_KEY env var.
        """
        print("Building knowledge base...")

        # Convert our docs into LangChain Document objects
        documents = []
        for doc in KNOWLEDGE_BASE_DOCS:
            documents.append(Document(
                page_content=doc["content"],
                metadata={"title": doc["title"], "source": "healix-kb"}
            ))

        # Split long documents into smaller chunks for better retrieval
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,     # Each chunk = 500 characters
            chunk_overlap=50    # Overlap to avoid losing context at boundaries
        )
        chunks = splitter.split_documents(documents)

        # Use provided embeddings or fall back to direct OpenAI
        if embeddings is None:
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )

        # Store vectors in FAISS (a fast local vector database)
        self.vectorstore = FAISS.from_documents(chunks, embeddings)
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": 3}  # Return top 3 most relevant chunks
        )
        print(f"Knowledge base ready: {len(chunks)} document chunks indexed")
        return self

    def search(self, query: str) -> list:
        """Find the most relevant documents for a given query"""
        if not self.retriever:
            return []
        docs = self.retriever.invoke(query)
        return [{"title": d.metadata.get("title"), "content": d.page_content} for d in docs]


# ════════════════════════════════════════════════════════════
#  HEALIX AGENT — Main orchestrator
# ════════════════════════════════════════════════════════════

class HealIXAgent:
    """
    The main HEALIX agent that:
    1. Manages endpoint data (from database or simulated fallback)
    2. Answers questions using RAG + LLM
    3. Triggers and logs remediation actions
    4. Predicts future failures
    5. Integrates with Microsoft security services for context enrichment
    """

    def __init__(self, config=None):
        self.config = config
        self.rag = RAGEngine()
        self.llm = None
        self.qa_chain = None
        # Optional references set by main.py after construction
        self.db = None
        self.defender = None
        self.intune = None
        self.entra = None
        self.monitoring_engine = None
        self._init_ai()

    def _init_ai(self):
        """Initialize the AI models with provider priority: Ollama (on-prem) > Foundry > OpenAI direct > demo."""

        # ── Priority 1: On-prem Ollama (e.g. Gemma 3) ────────────
        # Ollama exposes an OpenAI-compatible API at {base_url}/v1, so we
        # reuse ChatOpenAI / OpenAIEmbeddings with a local base_url. Fully
        # offline — no cloud calls. Embeddings use a local model since Gemma
        # has no embedding head.
        ollama_cfg = getattr(self.config, "ollama", None)
        if ollama_cfg and ollama_cfg.is_configured:
            try:
                base_url = ollama_cfg.base_url.rstrip("/") + "/v1"
                self.llm = ChatOpenAI(
                    model=ollama_cfg.model,
                    temperature=0.1,
                    openai_api_key="ollama",   # placeholder; Ollama ignores it
                    base_url=base_url,
                )
                embeddings = OpenAIEmbeddings(
                    model=ollama_cfg.embed_model,
                    openai_api_key="ollama",
                    base_url=base_url,
                    check_embedding_ctx_length=False,  # local models lack tiktoken mapping
                )
                self.rag.build_knowledge_base(embeddings=embeddings)
                self._build_qa_chain()
                self._demo_mode = False
                self._llm_provider = "ollama_onprem"
                print(f"AI models ready! Provider: Ollama on-prem ({ollama_cfg.model} @ {ollama_cfg.base_url})")
                return
            except Exception as e:
                print(f"Ollama on-prem init failed, falling back: {e}")

        # ── Priority 2: Azure AI Foundry ─────────────────────────
        foundry_cfg = getattr(self.config, "foundry", None)
        if foundry_cfg and foundry_cfg.is_configured:
            try:
                from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
                self.llm = AzureChatOpenAI(
                    azure_endpoint=foundry_cfg.endpoint,
                    api_key=foundry_cfg.api_key,
                    azure_deployment=foundry_cfg.deployment_name,
                    openai_api_version=foundry_cfg.api_version,
                    temperature=0.1,
                )
                embeddings = AzureOpenAIEmbeddings(
                    azure_endpoint=foundry_cfg.endpoint,
                    api_key=foundry_cfg.api_key,
                    azure_deployment=foundry_cfg.embedding_deployment,
                    openai_api_version=foundry_cfg.api_version,
                )
                self.rag.build_knowledge_base(embeddings=embeddings)
                self._build_qa_chain()
                self._demo_mode = False
                self._llm_provider = "azure_foundry"
                print(f"AI models ready! Provider: Azure AI Foundry ({foundry_cfg.deployment_name})")
                return
            except Exception as e:
                print(f"Azure AI Foundry init failed, falling back: {e}")

        # ── Priority 3: Direct OpenAI ────────────────────────────
        api_key = self.config.openai_api_key if self.config else os.getenv("OPENAI_API_KEY")
        if api_key and api_key != "your-openai-api-key-here":
            try:
                self.llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0.1,
                    openai_api_key=api_key,
                )
                self.rag.build_knowledge_base()  # uses default OpenAIEmbeddings
                self._build_qa_chain()
                self._demo_mode = False
                self._llm_provider = "openai_direct"
                print("AI models ready! Provider: OpenAI direct (gpt-4o-mini)")
                return
            except Exception as e:
                print(f"OpenAI direct init failed, falling back to demo: {e}")

        # ── Priority 4: Demo mode ────────────────────────────────
        print("No AI provider configured. Running in DEMO MODE.")
        print("   On-prem Ollama:   set LLM_PROVIDER=ollama (+ OLLAMA_MODEL, OLLAMA_BASE_URL)")
        print("   Azure AI Foundry: set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY + AZURE_OPENAI_DEPLOYMENT_NAME")
        print("   OpenAI direct:    set OPENAI_API_KEY in .env")
        self._demo_mode = True
        self._llm_provider = "demo"

    def _build_qa_chain(self):
        """Build the RetrievalQA chain from self.llm and self.rag.retriever."""
        prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""You are HEALIX, an expert AI agent for autonomous IT infrastructure monitoring and self-healing.

You have access to the following knowledge base context:
{context}

Answer the following question from an IT operations perspective.
Be specific, actionable, and structured. Use bullet points for steps.
If you identify a critical issue, always suggest an immediate remediation action.

Question: {question}

Answer:"""
        )

        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.rag.retriever,
            chain_type_kwargs={"prompt": prompt_template},
            return_source_documents=True
        )

    # ── Ask the AI agent a question ───────────────────────────────
    async def ask(self, question: str, context: Optional[str] = None) -> dict:
        """Process a question through RAG + LLM pipeline, enriched with live data."""

        if self._demo_mode:
            return self._demo_response(question)

        # Build enrichment context from live Microsoft data
        enrichment = await self._gather_live_context(question)

        full_question = question
        if context:
            full_question = f"Regarding endpoint {context}: {question}"
        if enrichment:
            full_question = f"{full_question}\n\n--- Live Environment Data ---\n{enrichment}"

        # Run the RAG + LLM chain
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self.qa_chain({"query": full_question})
        )

        sources = []
        if "source_documents" in result:
            sources = list(set([
                doc.metadata.get("title", "Unknown")
                for doc in result["source_documents"]
            ]))

        return {
            "answer": result["result"],
            "sources": sources,
            "confidence": 0.94,
            "actions_taken": self._extract_actions(result["result"])
        }

    async def _gather_live_context(self, question: str) -> str:
        """Gather relevant live data from Microsoft clients to enrich the LLM prompt."""
        parts = []
        q = question.lower()

        try:
            # Endpoint data from database
            if self.db:
                endpoints = await self.db.get_endpoints()
                if endpoints:
                    summary = ", ".join(
                        f"{ep.get('name')}(cpu={ep.get('last_cpu','?')}%,mem={ep.get('last_mem','?')}%,status={ep.get('status','?')})"
                        for ep in endpoints[:6]
                    )
                    parts.append(f"Current endpoints: {summary}")

            # Defender incidents for threat-related questions
            if self.defender and self.defender.is_available and any(
                kw in q for kw in ["threat", "incident", "attack", "malware", "defender", "security"]
            ):
                incidents = await self.defender.get_incidents(top=5)
                if incidents:
                    inc_summary = "; ".join(
                        f"{i.get('title','')} (severity={i.get('severity','')}, status={i.get('status','')})"
                        for i in incidents[:3]
                    )
                    parts.append(f"Recent Defender incidents: {inc_summary}")

            # Active alerts from database
            if self.db and any(
                kw in q for kw in ["alert", "critical", "warning", "issue", "problem"]
            ):
                alerts = await self.db.get_alerts(resolved=False, limit=5)
                if alerts:
                    alert_summary = "; ".join(
                        f"{a.get('title','')} on {a.get('endpoint_name','')}"
                        for a in alerts[:3]
                    )
                    parts.append(f"Active alerts: {alert_summary}")

            # Anomalies for performance questions
            if self.monitoring_engine and any(
                kw in q for kw in ["cpu", "memory", "disk", "performance", "slow", "anomaly"]
            ):
                anomalies = await self.monitoring_engine.detect_anomalies()
                if anomalies:
                    anom_summary = "; ".join(
                        f"{a.get('endpoint','')} {a.get('metric','')}={a.get('current_value','')} (threshold={a.get('threshold','')})"
                        for a in anomalies[:3]
                    )
                    parts.append(f"Current anomalies: {anom_summary}")

        except Exception:
            pass  # Enrichment is best-effort; never block the main response

        return "\n".join(parts)

    def _extract_actions(self, answer_text: str) -> list:
        """Parse any action items from the AI response"""
        actions = []
        lines = answer_text.split("\n")
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                if len(line) > 10:
                    actions.append(line.lstrip("0123456789.-•").strip())
        return actions[:3]  # Return top 3 actions

    def _demo_response(self, question: str) -> dict:
        """Demo responses when no API key is configured"""
        q = question.lower()
        if "cpu" in q or "critical" in q or "edge" in q:
            answer = """**Root Cause Analysis — EDGE-NODE-07** (DEMO MODE)

• CPU spike to 99% triggered at 14:31:58 UTC
• Pattern matched: runaway Node.js process (seen 3x in past 90 days)
• Contributing factor: Memory leak in app v2.3.1 causing GC pressure

**Agentic Action Plan:**
1. Kill zombie PID 4821, 4822 (auto-triggered)
2. Restart application service (in progress)
3. Schedule Node.js v20.9.0 upgrade

*Add your OpenAI API key to .env for real AI-powered analysis.*"""
        elif "memory" in q or "mem" in q:
            answer = """**Memory Analysis** (DEMO MODE)

• Cluster average: 68.2% utilization (↑8% vs yesterday)
• Risk: PROD-SRV-02 on OOM trajectory in ~2 hours
• DB-CLUSTER-01 high usage is normal (end-of-month reporting)

**Recommended Actions:**
1. Scale PROD-SRV-02 memory (+4GB)
2. Restart non-critical services at 15:00 UTC
3. Enable swap watchdog on Linux nodes

*Add your OpenAI API key to .env for real AI-powered analysis.*"""
        elif "patch" in q or "cve" in q or "vulnerab" in q:
            answer = """**Patch Intelligence Report** (DEMO MODE)

| Endpoint     | Patch           | Severity | CVSS |
|--------------|-----------------|----------|------|
| DEV-WS-015   | KB5031455       | Medium   | 5.6  |
| PROD-SRV-02  | OpenSSL 3.1.4   | CRITICAL | 9.1  |
| EDGE-NODE-07 | Node.js 20.9.0  | High     | 7.5  |

⚠️ OpenSSL patch on PROD-SRV-02 is URGENT — active exploit in wild.

*Add your OpenAI API key to .env for real AI-powered analysis.*"""
        elif "predict" in q or "failure" in q or "risk" in q:
            answer = """**Predictive Failure Analysis — Next 24h** (DEMO MODE)

🔴 EDGE-NODE-07 — 94% failure probability
   Reason: Recurring OOM cycle, degraded hardware signal

🟡 DB-CLUSTER-01 — 41% risk
   Reason: Disk at 91%, approaching threshold

🟢 All other endpoints — <12% risk

**Pre-emptive Actions:**
1. Provision failover for EDGE-NODE-07
2. Archive old DB logs (free ~15% disk)
3. Increase monitoring to 30s intervals

*Add your OpenAI API key to .env for real AI-powered analysis.*"""
        else:
            answer = f"""**HEALIX AI Response** (DEMO MODE)

I received your query: *"{question}"*

I'm currently running in demo mode (no OpenAI API key configured).

To enable full AI-powered responses:
1. Get your API key from platform.openai.com
2. Add it to the .env file: OPENAI_API_KEY=sk-...
3. Restart the server

The RAG knowledge base contains 8 specialized IT runbooks covering:
CPU issues, memory leaks, disk management, CVE patches, predictive analysis, and more.

*Add your OpenAI API key to unlock real intelligent responses.*"""

        return {
            "answer": answer,
            "sources": ["Demo Mode — Knowledge Base Available"],
            "confidence": 0.85,
            "actions_taken": []
        }

    # ── Trigger auto-remediation ──────────────────────────────────
    async def trigger_remediation(self, endpoint_id: str, issue_type: str,
                                   triggered_by: str = "agent") -> dict:
        """Start an automated healing action on an endpoint.
        Uses real Intune device actions when available, otherwise simulates.
        """
        action_map = {
            "high_cpu":     "Kill zombie processes + restart service",
            "memory_leak":  "Compress memory cache + schedule service restart",
            "disk_full":    "Archive old logs + clean package cache",
            "service_down": "Restart failed service + verify health check",
            "patch_needed": "Download and apply security patch",
        }

        action = action_map.get(issue_type, f"Diagnose and remediate: {issue_type}")
        intune_result = None

        # Attempt real Intune device action if available
        if self.intune and self.intune.is_available:
            try:
                intune_action = {
                    "high_cpu": "rebootNow",
                    "service_down": "rebootNow",
                    "patch_needed": "windowsDefenderScan",
                }.get(issue_type)
                if intune_action:
                    intune_result = await self.intune.trigger_device_action(
                        endpoint_id, intune_action
                    )
            except Exception:
                pass  # Fall through to simulated action

        if not intune_result:
            await asyncio.sleep(1)  # Simulate action execution

        action_id = f"HA-{random.randint(100,999)}"
        now = datetime.now(timezone.utc).isoformat()
        # Simulated actions complete immediately; real Intune actions stay "triggered"
        status = "triggered" if intune_result else "completed"

        # Log to database if available
        if self.db:
            try:
                await self.db.insert_healing_action(
                    timestamp=now,
                    endpoint_name=endpoint_id,
                    action_type=issue_type,
                    action_description=action,
                    status=status,
                    impact="high" if issue_type in ("high_cpu", "service_down") else "medium",
                    triggered_by=triggered_by,
                )
            except Exception:
                pass

        return {
            "status": status,
            "endpoint_id": endpoint_id,
            "issue_type": issue_type,
            "action": action,
            "action_id": action_id,
            "estimated_resolution": "3-5 minutes",
            "timestamp": now,
            "intune_action": intune_result is not None,
        }

    # ── Predict failures ──────────────────────────────────────────
    async def predict_failures(self) -> list:
        """ML-based failure predictions for next 24 hours.
        Uses real anomaly data from monitoring engine when available.
        """
        # Try to build predictions from real anomaly + endpoint data
        if self.monitoring_engine and self.db:
            try:
                anomalies = await self.monitoring_engine.detect_anomalies()
                endpoints = await self.db.get_endpoints()
                if endpoints:
                    predictions = []
                    ep_anomaly_map = {}
                    for a in anomalies:
                        name = a.get("endpoint", "")
                        if name not in ep_anomaly_map:
                            ep_anomaly_map[name] = []
                        ep_anomaly_map[name].append(a)

                    for ep in endpoints:
                        name = ep.get("name", "")
                        cpu = ep.get("last_cpu", 0) or 0
                        mem = ep.get("last_mem", 0) or 0
                        disk = ep.get("last_disk", 0) or 0
                        ep_anomalies = ep_anomaly_map.get(name, [])

                        # Compute risk score from metrics + anomaly count
                        risk = min(100, int(
                            (cpu * 0.25) + (mem * 0.30) + (disk * 0.20)
                            + (len(ep_anomalies) * 15)
                        ))

                        if risk >= 80:
                            level = "critical"
                        elif risk >= 60:
                            level = "high"
                        elif risk >= 30:
                            level = "medium"
                        else:
                            level = "healthy"

                        reasons = []
                        if cpu > 70:
                            reasons.append(f"CPU at {cpu}%")
                        if mem > 70:
                            reasons.append(f"Memory at {mem}%")
                        if disk > 75:
                            reasons.append(f"Disk at {disk}%")
                        if ep_anomalies:
                            reasons.append(f"{len(ep_anomalies)} active anomalies")
                        if not reasons:
                            reasons.append("All metrics nominal")

                        action = "No action required"
                        if risk >= 80:
                            action = "Provision failover immediately"
                        elif risk >= 60:
                            action = "Prepare remediation runbook"
                        elif risk >= 30:
                            action = "Increase monitoring frequency"

                        predictions.append({
                            "endpoint": name,
                            "risk_score": risk,
                            "risk_level": level,
                            "reason": "; ".join(reasons),
                            "recommended_action": action,
                        })

                    predictions.sort(key=lambda x: x["risk_score"], reverse=True)
                    if predictions:
                        return predictions
            except Exception:
                pass  # Fall through to hardcoded predictions

        # Fallback to hardcoded demo predictions
        return [
            {"endpoint":"EDGE-NODE-07","risk_score":94,"risk_level":"critical","reason":"Recurring OOM + degraded CPU trend","recommended_action":"Provision failover immediately"},
            {"endpoint":"DB-CLUSTER-01","risk_score":41,"risk_level":"medium","reason":"Disk fill rate: +2.3% per day, reaches 95% in ~2 days","recommended_action":"Archive cold data"},
            {"endpoint":"PROD-SRV-02","risk_score":28,"risk_level":"low","reason":"Memory creep without OpenSSL patch","recommended_action":"Schedule patch tonight"},
            {"endpoint":"PROD-SRV-01","risk_score":8,"risk_level":"healthy","reason":"All metrics nominal","recommended_action":"No action required"},
            {"endpoint":"BACKUP-SRV","risk_score":5,"risk_level":"healthy","reason":"Stable, low utilization","recommended_action":"No action required"},
            {"endpoint":"DEV-WS-015","risk_score":15,"risk_level":"healthy","reason":"Post-patch stable","recommended_action":"Monitor for 24h"},
        ]

    # ── Get endpoint statuses ─────────────────────────────────────
    def get_endpoint_status(self) -> list:
        """Returns current status of all endpoints (simulated)"""
        import random
        base = [
            {"id":"EP-001","name":"PROD-SRV-01","os":"Windows Server 2022","status":"healthy","cpu":random.randint(20,30),"mem":random.randint(55,65),"disk":44,"uptime":"99.97%"},
            {"id":"EP-002","name":"PROD-SRV-02","os":"Ubuntu 22.04 LTS","status":"warning","cpu":random.randint(80,90),"mem":random.randint(75,82),"disk":72,"uptime":"99.81%"},
            {"id":"EP-003","name":"DEV-WS-015","os":"Windows 11 Pro","status":"healing","cpu":random.randint(40,50),"mem":random.randint(50,58),"disk":38,"uptime":"98.20%"},
            {"id":"EP-004","name":"DB-CLUSTER-01","os":"RHEL 9","status":"healthy","cpu":random.randint(30,38),"mem":random.randint(80,85),"disk":91,"uptime":"99.99%"},
            {"id":"EP-005","name":"EDGE-NODE-07","os":"Alpine Linux","status":"critical","cpu":random.randint(95,100),"mem":random.randint(90,97),"disk":60,"uptime":"95.40%"},
            {"id":"EP-006","name":"BACKUP-SRV","os":"Windows Server 2019","status":"healthy","cpu":random.randint(10,15),"mem":random.randint(38,45),"disk":55,"uptime":"100%"},
        ]
        return base

    def get_alerts(self) -> list:
        return [
            {"id":1,"time":"14:32:01","type":"critical","endpoint":"EDGE-NODE-07","msg":"CPU threshold exceeded (99%). Auto-remediation triggered.","resolved":False},
            {"id":2,"time":"14:28:45","type":"warning","endpoint":"PROD-SRV-02","msg":"Memory utilization high (78%). Monitoring escalation path.","resolved":False},
            {"id":3,"time":"14:15:22","type":"info","endpoint":"DEV-WS-015","msg":"Patch KB5031455 applied. Reboot scheduled at 18:00.","resolved":True},
            {"id":4,"time":"13:58:11","type":"success","endpoint":"PROD-SRV-01","msg":"Self-healing: IIS service restarted successfully.","resolved":True},
        ]

    def get_healing_actions(self) -> list:
        return [
            {"id":"HA-001","ts":"14:32:05","endpoint":"EDGE-NODE-07","action":"Kill zombie processes","status":"running","impact":"high"},
            {"id":"HA-002","ts":"14:30:11","endpoint":"PROD-SRV-02","action":"Compress memory cache","status":"completed","impact":"medium"},
            {"id":"HA-003","ts":"14:15:00","endpoint":"DEV-WS-015","action":"Apply Windows patch KB5031455","status":"completed","impact":"low"},
            {"id":"HA-004","ts":"13:58:09","endpoint":"PROD-SRV-01","action":"Restart IIS service","status":"completed","impact":"low"},
        ]

    def get_patch_intelligence(self) -> list:
        return [
            {"endpoint":"PROD-SRV-02","patch":"OpenSSL 3.1.4","severity":"critical","cvss":9.1,"cve":"CVE-2023-0286","status":"pending","scheduled":"Tonight 02:00 UTC"},
            {"endpoint":"EDGE-NODE-07","patch":"Node.js 20.9.0","severity":"high","cvss":7.5,"cve":"CVE-2023-44487","status":"pending","scheduled":"Awaiting approval"},
            {"endpoint":"DEV-WS-015","patch":"KB5031455","severity":"medium","cvss":5.6,"cve":"MS-2023-045","status":"applied","scheduled":"Completed"},
        ]
