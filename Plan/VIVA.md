# Clario System VRAM Requirements & Hosting Feasibility

If we want to host the full Clario ML Sidecar in the cloud **with all local AI models running purely on GPU hardware** (bypassing the Gemini API completely), here is the exact breakdown of the VRAM (Video RAM) calculations required.

---

## Viva Impact Note: Duplicate Tickets and Sequential Processing

### The Problem We Had
When many users submitted the same issue, the system still routed each ticket through the full ML pipeline. That meant repeated calls to redaction, routing, Gemma classification, retrieval, and escalation logic, even when the answer had already been found earlier. In practice, the worker also hardcoded tickets as escalated, so resolved tickets did not cleanly finish as completed/resolved.

### Strategy We Used
We fixed the pipeline in two places:
1. The worker now respects the real escalation result from the graph instead of forcing every ticket into the escalated path.
2. Resolved tickets are automatically embedded into precedent memory, using redacted and normalized text, so the next similar ticket can reuse the previous answer.
3. The duplicate check now compares normalized semantic text and uses a slightly more tolerant similarity gate, so paraphrased versions are more likely to match the same cluster.

### Logic Behind It
1. First ticket in a cluster runs the full pipeline once.
2. The final answer is stored as precedent memory.
3. The next ticket with the same or strongly similar meaning is checked against the semantic cache before doing expensive downstream work.
4. If the similarity score is high enough, the system reuses the earlier answer instead of recomputing one from scratch.

### Impact Numbers for Viva
Use this simple example:
- Without the fix: 100 repeated tickets = 100 full pipeline runs.
- With the fix: 1 full pipeline run + 99 cache hits.

If one full ticket takes about 45 seconds and a cache hit takes about 1 second, then:
- Before: 100 × 45s = 4,500s = 75 minutes.
- After: 45s + 99 × 1s = 144s = 2.4 minutes.
- Time saved: 4,356s = 72.6 minutes.
- Reduction: about 96.8%.

That is the main viva point: the system becomes sequential for GPU safety, but repeated issue clusters are answered almost immediately after the first resolution is stored.

## 1. Local LLM: Classification & Sentiment (`google/gemma-3-1b-it`)
*   **Parameter Count:** 1 Billion parameters
*   **Precision:** Loaded in native `bfloat16` (16-bit precision)
*   **Weight Memory:** 1 Billion × 2 bytes = **2.0 GB**
*   **KV Cache & Context Memory:** ~0.5 GB (during inference)
*   **Total VRAM:** **~2.5 GB**

## 2. Vision-Language Model: OCR Extraction (`Qwen/Qwen2-VL-2B-Instruct`)
*   **Parameter Count:** 2 Billion parameters
*   **Precision:** 4-bit Quantization (`bitsandbytes` NF4 double-quantization)
*   **Weight Memory:** 2 Billion × 0.5 bytes = **1.0 GB**
*   **Vision Encoder & Activation Memory:** ~0.8 GB (Vision Transformers require higher activation memory for image patches)
*   **Total VRAM:** **~1.8 GB**

## 3. RAG Embedding Model (`all-MiniLM-L6-v2`)
*   **Parameter Count:** 22 Million parameters
*   **Precision:** `float32` (default)
*   **Weight Memory:** ~90 MB
*   **Total VRAM:** **~0.1 GB** (Can also be easily offloaded to CPU RAM with 0 latency hit)

## 4. CUDA Context Overhead
*   Initializing PyTorch and reserving memory blocks for the CUDA environment universally requires overhead per GPU process.
*   **Total VRAM:** **~0.8 GB**

---

## 🧮 Total VRAM Calculation
**2.5 GB (Gemma) + 1.8 GB (Qwen) + 0.1 GB (Embeddings) + 0.8 GB (CUDA Overhead) = 5.2 GB Total VRAM.**

### Conclusion for Hosting:
To host the Clario backend with all local models running concurrently in memory without thrashing (offloading to slower CPU RAM), the cloud server requires a GPU with an absolute minimum of **6 GB of VRAM**. 

A standard **8 GB VRAM GPU** (such as an NVIDIA RTX 3060, RTX 4060, or a cloud-based NVIDIA T4 which has 16GB) is the highly recommended baseline for production stability. 

### Why the Free Tier Fails:
Cloud providers like Render or Heroku offer 0 GB of VRAM and only 512MB of standard CPU RAM on their free tiers. Attempting to load even a 4-bit quantized 2B parameter model will instantly crash the container due to out-of-memory (OOM) exceptions.

---

## 💰 Cloud Hosting Cost Analysis (Per Month)
If you deploy this architecture to a cloud provider, you must provision an instance with a dedicated GPU (e.g., an NVIDIA T4 16GB or RTX 4000 series 8GB). Here is the estimated 24/7 monthly cost across major platforms:

1. **Amazon Web Services (AWS) — ~$384 / month**
   *   **Instance:** `g4dn.xlarge` (NVIDIA T4 16GB VRAM, 4 vCPU, 16GB RAM)
   *   **Cost:** ~$0.526 per hour.

2. **Google Cloud Platform (GCP) — ~$394 / month**
   *   **Instance:** `n1-standard-4` + 1x NVIDIA T4 GPU attached.
   *   **Cost:** ~$0.35 (GPU) + ~$0.19 (Compute) = ~$0.54 per hour.

3. **DigitalOcean (Paperspace) — ~$365 / month**
   *   **Instance:** Core VM with NVIDIA Quadro P4000 (8GB VRAM).
   *   **Cost:** ~$0.51 per hour.

4. **RunPod / Vast.ai (Best for ML Startups) — ~$146 / month**
   *   **Instance:** Community Cloud / Serverless with RTX 3060 (12GB) or T4.
   *   **Cost:** ~$0.20 per hour.
   *   *Note: Using RunPod Serverless, you only pay per second of execution. If your support volume is low, actual costs could drop to **under $20/month**.*

---

## 🚀 The Hybrid Strategy (Keep Gemma, API for OCR)

During the viva, a great architectural point to bring up is the **Hybrid Strategy**. 

If you keep `Gemma-3-1b` running locally for strict data privacy during classification, but replace the massive `Qwen2-VL` (OCR) with the **Gemini API**, the system architecture changes significantly:

1.  **VRAM Requirement drops to ~3.4 GB:** 
    *   Gemma (~2.5 GB) + Embeddings (~0.1 GB) + CUDA Overhead (~0.8 GB).
2.  **Hosting Impact:** 
    *   **Major Clouds (AWS/GCP):** The cost **does not change** (~$384/mo). This is because cloud providers like AWS do not rent out "half a GPU" or 4GB GPUs. Their smallest GPU instance is still the `g4dn.xlarge` (16GB VRAM), so you pay the same price regardless of if you use 3GB or 15GB of it.
    *   **Community Clouds (Vast.ai / RunPod):** The cost **drops significantly**. Because you only need 3.4 GB of VRAM, you can rent much older, cheaper consumer GPUs (like an NVIDIA GTX 1060 6GB or a partitioned RTX 3060). This drops the hosting cost from ~$146/mo down to roughly **~$30 to $50 / month**.
3.  **Gemini API Cost:** Gemini 3.1 Flash-Lite has an extremely generous Free Tier. Even if exceeded, the cost for image OCR is fractions of a cent per ticket.

**The Trade-off:** 
You maintain 100% data privacy for all text-based tickets (since Gemma handles them locally), while only sacrificing privacy for tickets that specifically contain image attachments.

---

## ⚖️ Load Balancing & Scalability (The "500 Ticket" Scenario)

If 500 users submit tickets simultaneously, how does the system balance the load without crashing the local GPU?

This is where the microservice architecture shines. The system handles massive spikes elegantly using a **Producer-Consumer Queue** model:

1. **The Producer (Spring Boot Gateway):**
   When 500 users click "Submit", the Next.js frontend sends 500 simultaneous HTTP requests to the Java Spring Boot API Gateway. Java Spring Boot (running on Tomcat) handles thousands of concurrent threads easily. It accepts all 500 requests instantly and pushes the ticket payloads directly into the **Redis `ticket_queue`**. It does *not* wait for the AI to finish, so the users get an immediate "Ticket Submitted" response on the frontend.
2. **The Buffer (Redis):**
   Redis is an ultra-fast, in-memory data store. It safely buffers all 500 tickets in a queue. Redis can handle over 100,000 operations per second, so the massive spike in traffic is absorbed effortlessly.
3. **The Consumer (Python ML Worker):**
   The ML Sidecar (`worker.py`) uses a blocking pop command (`brpop`) to pull tickets from the Redis queue. Crucially, the Python worker is configured to `await` the processing of each ticket sequentially. 
   *   Because it processes exactly **1 ticket at a time**, the GPU VRAM is never overloaded (preventing Out-Of-Memory crashes).
   *   The GPU operates at exactly 100% utilization, churning through the queue one by one until all 500 are resolved.

**How to Scale Up:**
If resolving 500 tickets sequentially takes too long, you simply spin up *more* ML worker instances on additional GPU servers. Because Redis `brpop` is an atomic operation, multiple workers can safely pull from the exact same queue simultaneously without ever processing the same ticket twice. This is horizontal scaling at its finest!

---

## 🏗️ Phase 2: From Monolith to Microservices (Viva Pitch)

During the viva, you can confidently explain the roadmap for Phase 2: officially transitioning the architecture into a fully containerized **Domain-Driven Microservices** setup. 

### 1. The Problem with the Current "Monolithic" Structure
While the system is currently decoupled by language (Java vs. Python), the internal codebases are too bundled:
*   **Resource Contention (The biggest issue):** In the current `clario-ml-sidecar`, both `Gemma-3-1b` and `Qwen2-VL` are loaded into the exact same Python process. They fight for the same pool of VRAM. If a massive spike of images comes in, the process could crash, taking down the text classification capabilities with it.
*   **Coupled Deployments:** If a developer updates the RAG prompt in `local_llm.py`, they have to reboot the entire Python server, momentarily taking down the OCR tool as well.

### 2. The Decision: Feasibility of Microservices
The panel will ask: *"Is it actually feasible to convert this?"*
Your answer: **Yes, it is extremely feasible because we do not need to change our tech stack.**
*   We already use the industry-standard microservice glue: **Redis** and **REST (FastAPI/Spring Boot)**.
*   The transition only requires reorganizing our existing code into smaller folders (e.g., extracting the Java API Gateway from the Java Ticket Core) and wrapping each folder in a `Dockerfile`.

### 3. How the "Hybrid Strategy" Makes This Easier
Adopting the **Hybrid Strategy** (keeping Gemma local, moving OCR to the Gemini API) makes the Microservices migration significantly easier:
*   Instead of having to provision two separate GPU microservices (one for Gemma, one for Qwen), we only need **one small GPU microservice** (for Gemma).
*   The OCR microservice simply becomes a lightweight Python API that forwards Base64 images to Google's Gemini servers. This removes the VRAM contention problem entirely and cuts our required cloud hosting costs drastically, making our enterprise deployment highly cost-effective and structurally resilient.
