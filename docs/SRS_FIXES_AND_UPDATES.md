# Clario SRS Document Review & Fixes

This document outlines the comprehensive A-Z fixes required for the `Clario - Software Requirements Specification` to align it with the actual project specifications defined in the `SOFTWARE_ARCHITECTURE_DOCUMENT.md` (SAD) and the Feasibility Study. 

The current SRS reads very much like a raw, AI-generated template (containing placeholders like `<Company Name>`) and lacks the specific proprietary architectures your team has designed (like SurrogateShield, Semantic Distillation, and Evidence Graph Consistency).

Apply the following fixes from top to bottom before submission to ensure the SRS accurately reflects your Group 23 project and looks like it was written by the engineering team.

## 1. Title Page & Document Control (Remove Template Placeholders)
**Current Issue:** The cover page and revision history contain raw placeholders (`<Company Name>`, `<details>`) which is a clear hallmark of unedited AI generation.
**Fixes:**
*   **Cover Page:** 
    *   Change `<Company Name>` to `Group 23`.
    *   Change `<Project Name>` to `Clario`.
    *   Change `<Project/System/Feature>` to `A Multi-Agent Customer Support Triage and Response System`.
    *   Add the context from the Feasibility Study: `CS3501 Data Science and Engineering Project — Group 23, P04`.
    *   Add the team members: `WEERASEKARA R.V. (230694J), WETTASINGHE V.N. (230701G), WICKRAMARATNA S.I.P. (230703N)`.
    *   Add the Mentor (`Dr. Aloka Fernando`) and TA (`Dilanka`).
*   **Revision History:** Replace `<details>` with a proper description like `Initial draft for CS3501 submission`.

## 2. Section 1: Introduction
**Current Issue:** Generic descriptions and an incorrect project scope regarding the Rysera LMS.
**Fixes:**
*   **1.2 Scope:** 
    *   **Remove/Demote Rysera LMS:** The SRS states Rysera STEM LMS is the "initial deployment target". The SAD clearly states this is only a **"Stretch Goal"** (SAD Section 23). State that it is a standalone system with potential stretch integration for Rysera.
    *   **Inject Team Terminology:** Update the scope bullet points to use the team's specific mechanisms: *SurrogateShield* for PII masking, *Semantic Distillation* for ticket analysis, and *Evidence Graph Consistency (EGC)* for validation.
*   **1.3 Definitions, Acronyms, and Abbreviations:** 
    *   Add **SurrogateShield**: Deterministic PII masking engine using Regex and spaCy NER.
    *   Add **Semantic Distillation**: Process of extracting structured key phrases to eliminate lexical noise before classification.
    *   Add **EGC (Evidence Graph Consistency)**: Validation mechanism to check for structural detachment and hallucinations.
    *   Add **ResolvePass**: Agent responsible for restoring original PII from the ShadowMap.
    *   Add **ShadowMap**: AES-256 encrypted mapping of PII to surrogates.
    *   Add **QLoRA**: Parameter-efficient fine-tuning technique used for the local classifier.

## 3. Section 2: Overall Description
**Current Issue:** Generic technology stack that misaligns with the detailed SAD decisions.
**Fixes:**
*   **2.1 Product Perspective:** 
    *   Update the frontend bullet point from "Web-based frontend application" to `React (Next.js) + TypeScript + Tailwind CSS` to align with the Feasibility Study and the hybrid monolith architecture.
    *   Update the Fine-Tuned Model bullet to `Fine-Tuned Classification Model Service (Mistral-7B / Llama-3-8B via QLoRA)`.
*   **2.2 Product Functions:** 
    *   *Personally Identifiable Information (PII) Protection:* Explicitly name this the `SurrogateShield` process. Mention it uses AES-256 ShadowMaps.
    *   *Automated Ticket Analysis:* Mention it performs `Semantic Distillation` prior to passing to the fine-tuned LLM.
    *   *Response Validation:* Name the processes `Reference-Guided CoT LLM-as-judge` and `Evidence Graph Consistency (EGC)`.
    *   *Human Review and Escalation:* Add a bullet point for `Optimistic Locking (HTTP 409 Conflict handling)` to prevent concurrent editing race conditions between human agents and AI.
*   **2.4 Operating Environment:** 
    *   *Frontend Environment:* Keep `Next.js`. Ensure `React 18`, `TypeScript` and `Tailwind CSS` are explicitly listed.
    *   *AI Environment:* Specify `Mistral-7B-Instruct-v0.3 / Llama-3-8B (LoRA adapter)` and `Google Gemini 2.5 Flash / Flash Lite`. Specify `sentence-transformers/all-MiniLM-L6-v2` instead of just "Sentence Transformer".

## 4. Section 3: Specific Requirements (Functional)
**Current Issue:** The flow descriptions are highly generic ("ticket text is analyzed"). They need to reflect your specific LangGraph nodes and architecture.
**Fixes:**
*   **FR-008 - Automatic Ticket Classification:** Update the Main Flow to state that the system performs a single-pass classification using the fine-tuned open-weight model, rather than a multi-turn LLM chain, to optimize latency.
*   **FR-013 & FR-014 - PII Detection and Redaction:** Rename to reflect `SurrogateShield`. Update the main flow to state that Regex and spaCy NER are used to create deterministic surrogates, and mappings are stored in a secure ShadowMap.
*   **FR-015 - PII Restoration:** Rename to reflect `ResolvePass`. 
*   **FR-017 - Dynamic Agent Routing:** Update the flow to explicitly mention the routing nodes: `Technical`, `Billing`, or `Both (Concurrent execution)`. Add the specific **v3 Reroute Logic**: *If a misroute occurs, the system performs an Explicit Domain Flip rather than re-evaluating the route to prevent infinite loops.*
*   **FR-025 - Knowledge Retrieval:** Add the exact constraints from the SAD: Retrieval uses `ChromaDB vector similarity search`, fetches `top_k=4` chunks, and applies a `relevance threshold of 0.30`.
*   **FR-029 & FR-030 - Response Quality & Hallucination Detection:** Update these to utilize the `Reference-Guided CoT Judge` and `Evidence Graph Consistency (EGC)`.
*   **FR-035 & FR-036 - Human Response Editing & Resolution:** Add a requirement for **Optimistic Locking**. The system must use a version column to prevent race conditions (HTTP 409) when a human agent edits a ticket concurrently with the system.

## 5. Section 3.4 & 3.6: Non-Functional Constraints
**Current Issue:** Missing the specific architectural drivers that make your project feasible at zero cost.
**Fixes:**
*   **PER-002 - AI Workflow Processing Time:** The requirement states 15 seconds. Ensure it notes that the local QLoRA single-pass classifier takes `~200ms` (from Feasibility Study) to keep total latency down.
*   **DC-002 - Technology Stack Constraints:** 
    *   Change frontend constraint from React + TypeScript to `React 18 (Next.js) + TypeScript + Tailwind CSS`.
    *   Change generic embedding statement to specifically require `all-MiniLM-L6-v2`.
*   **DC-003 - AI Processing Constraints:** Add the constraint that the project operates on a **zero-capital compute budget** (Kaggle/Colab free tiers for training, Gemini Free Tier for distillation) as outlined in the Feasibility Study.
*   **DC-019 - Desktop Application Constraints:** Ensure it clearly states that the Next.js static assets are served from the Spring Boot application.

## 6. General Cleanup & Formatting (De-AI the Document)
*   **Remove Empty "Alternative Flows":** Many requirements end with "Alternative Flows: None." If there are none, remove the section completely rather than leaving a "None" placeholder.
*   **Unify the Tone:** The SRS currently uses generic enterprise language. Bring in the academic tone used in the SAD and Feasibility Study (e.g., refer to "Multi-Agent orchestration", "Open-weight models", and "Knowledge Distillation").
*   **Add "Hybrid Monolith":** Make sure the term `Hybrid Monolith Architecture` is prominently used when describing how the Spring Boot app and Python FastAPI Sidecar interact, rather than generic "containerized microservices" terminology.

## Summary Checklist for Final PDF Generation
1. [ ] No `< >` placeholders remain.
2. [ ] All team members and course details are on the cover.
3. [ ] "Rysera LMS" is moved to a Stretch Goal.
4. [ ] Frontend stack is explicitly listed as React (Next.js) + TypeScript + Tailwind CSS.
5. [ ] SurrogateShield, Semantic Distillation, EGC, ResolvePass, and Optimistic Locking are explicitly mentioned in the functional flows.
6. [ ] Tech stack matches SAD Section 5 exactly.
