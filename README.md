# GoodFoods AI Reservation Agent

> **A Federated Agent Network for the Hospitality Industry**

GoodFoods is not just a chatbot—it's a demonstration of an **Agent-to-Agent (A2A)** ecosystem. Built from scratch without frameworks like LangChain, it uses a central "Concierge" agent to orchestrate specialized agents (Search, Booking) via a custom JSON-RPC protocol. This architecture enables interoperability, scalable vertical expansion, and "smart" features like automatic conflict resolution.

---


##  Setup Instructions

### Prerequisites
- Python 3.8+
- OpenAI API Key (gpt-4o-mini recommended)

### 1. Clone & Install
```bash
git clone <repository-url>
cd goodfoods
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini
```

### 3. Initialize Database
Populate the SQLite database with 75+ diverse restaurant locations:
```bash
python backend/init_database.py
```

### 4. Run Application
Launch the Streamlit frontend:
```bash
streamlit run app.py
```
Access the app at `http://localhost:8501`.

---

##  Prompt Engineering Documentation

The system relies on **two core prompts** to drive intelligence, designed with specific temperatures and constraints.

### 1. Intent Classification Prompt (`Temperature: 0.2`)
**Goal:** Deterministic routing and strict JSON output.
- **Context:** "You are an intelligent intent classifier..."
- **Instructions:**
  - Detect intent from 5 distinct categories (`find_restaurants`, `create_booking`, `modify_booking`, `cancel_booking`, `general_query`).
  - Extract entities: `cuisine`, `location`, `time` (ISO 8601), `party_size`, `booking_id`.
  - **Output Constraint:** Strict JSON schema required.
- **Why Low Temp?** We need consistent, machine-readable JSON to route tasks to the correct agent code.

### 2. Natural Language Response Prompt (`Temperature: 0.7`)
**Goal:** Engaging, varied, and helpful conversation.
- **Context:** "You are a friendly restaurant concierge assistant named Jarvis..."
- **Instructions:**
  - **Search Results:** "Write a descriptive paragraph (3-4 sentences)... use cuisine flag emojis... separate with `----`."
  - **Conflict Resolution:** "Be apologetic... suggest the alternative times provided."
  - **Tone:** Professional yet warm ("Like describing to a friend").
- **Why High Temp?** Allows for variety in phrasing so the bot doesn't sound robotic.

---

##  Example Conversations (User Journeys)

### Journey 1: The "Smart" Search (Discovery)
**User:** "I need a romantic Italian place downtown, under $100 for two."
**Jarvis:** 
> 1. **Luigi's Trattoria** 🇮🇹
> This is a fantastic choice for a romantic evening, located right in the heart of Downtown. It has a stellar rating of 4.5/5.0 and offers an intimate ambiance. The price range is moderate ($$/4), fitting perfectly within your budget.
> ----
> 2. **Bella Notte** 🇮🇹 ...

*(Logic: The Search Agent filtered by `cuisine=Italian`, `location=Downtown`, `ambiance=Romantic`, and calculated `price_range<=2` based on the $100 budget.)*

### Journey 2: The "Context-Aware" Booking
**User:** "Book the first one for 7pm tomorrow."
**Jarvis:** "I'd be happy to help! Could you please tell me your name?"
**User:** "Alex."
**Jarvis:** 
> Booking confirmed! 🎉
> **Restaurant:** Luigi's Trattoria
> **Time:** 7:00 PM tomorrow
> **Party Size:** 2 people (inferred from previous "under $100 for two")
> **Booking ID:** #1042

*(Logic: Client Agent resolved "first one" to `Luigi's`, inferred party size from conversation history, and paused execution to ask for the missing name.)*

### Journey 3: Conflict Resolution (Smart Suggestions)
**User:** "Book Luigi's for 7pm tonight."
**Jarvis:** 
> I'm sorry, but the 7:00 PM slot at Luigi's Trattoria is already booked. 😔
> However, I found these available times nearby: **6:00 PM** and **8:00 PM**.
> Would you like to book one of these instead?

*(Logic: Booking Agent detected a primary key conflict in the DB, ran a `find_alternative_times()` heuristic for ±2 hours, and returned them in the failure artifact.)*

### Journey 4: Modification & Update
**User:** "Actually, change that reservation to 8pm."
**Jarvis:** "Done! Your reservation (#1042) has been updated to 8:00 PM."

---

##  Business Strategy Summary
*For full details, see [STRATEGY.md](STRATEGY.md)*

**Vision:** GoodFoods is not building a chatbot; we are building an **"Agent-Ready" Infrastructure**. By exposing our inventory via standard Agent-to-Agent protocols, we position ourselves to be the default dining partner for future AI assistants (Siri, Gemini, etc.).

**Key Metrics & ROI:**
- **Task Success Rate (TSR):** Target >85% for autonomous bookings.
- **Conversion Lift:** Projected +15% by reducing booking friction (30s vs 5min phone call).
- **Support Savings:** 30% reduction in operational costs by automating modifications/cancellations.

**Vertical Expansion:**
The A2A protocol designed here is domain-agnostic. The same `Client` -> `Specialist` architecture can be white-labeled for **Healthcare** (Patient -> Scheduling Agent) or **Real Estate** (Buyer -> Viewing Agent).

---

##  Assumptions & Limitations

### Assumptions
1. **Single-User Session:** The current Streamlit implementation stores state in memory; refreshing the page clears context.
2. **Simplified Availability:** We assume a "slot" is a unique combination of (Restaurant + Time). We do not model individual tables/inventory depth for this demo.
3. **Time Handling:** All times are interpreted relative to "today" unless a date is specified.

### Limitations
1. **No Payment Processing:** Bookings are transactional in the DB but do not process real payments.
2. **SQLite Concurrency:** While functional for demos, the SQLite DB would need migration to PostgreSQL for high-concurrency production loads.
3. **Context Window:** The conversation history is currently capped at the last 10 turns to manage token usage.

### Future Enhancements
- [ ] **Multi-User Auth:** Persistent user profiles and booking history.
- [ ] **External Agent API:** Expose an HTTP endpoint for other agents (e.g., Uber Agent) to query our availability.
- [ ] **RAG Integration:** Vector search for semantic queries like "places with a quiet corner for meetings."
- [ ] **Voice Interface:** Speech-to-text layer for phone-based reservations.
