# AI Research Helper

AI Research Helper is a lightweight, academic-focused RAG (Retrieval-Augmented Generation) application designed for academics, analysts, and students to analyze PDFs, search arXiv journals, and consult the open web with session-based memory.

---

## 🛠️ Project Structure
```text
ai-research-helper/
├── app/
│   ├── __init__.py      # Package initialization
│   ├── main.py          # FastAPI entry point & API endpoints
│   ├── agent.py         # Conversational ReAct agent (gpt-3.5-turbo)
│   ├── memory.py        # In-memory ConversationBufferWindowMemory (k=10)
│   ├── retriever.py     # retrieval_tools (web_search, arxiv_search, pdf_search)
│   └── ingest.py        # PDF parser (PyMuPDF) & local Chroma embedding (all-MiniLM-L6-v2)
├── ui/
│   └── chat_app.py      # Streamlit native Chat UI
├── data/
│   └── uploads/         # Uploaded PDFs go here
├── .env.example         # Template environment file
├── requirements.txt     # Python requirements list
├── test_app.py          # Self-contained integration test suite
└── README.md            # Installation and setup guide
```

---

## 🚀 Installation & Setup

### 1. Prerequisite: Virtual Environment
Navigate into the project directory and create a virtual environment:
```bash
cd ai-research-helper
python -m venv venv
```
Activate the environment:
* **On Windows (PowerShell/CMD):**
  ```powershell
  venv\Scripts\activate
  ```
* **On macOS/Linux:**
  ```bash
  source venv/bin/activate
  ```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Keys & Environment Variables
Copy `.env.example` to `.env`:
```bash
# On Windows (cmd):
copy .env.example .env
# On Windows (PowerShell) / macOS / Linux:
cp .env.example .env
```
Open `.env` in an editor and fill in your keys:
```env
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

#### How to get API Keys:
1. **OpenAI Key**: Log in to [platform.openai.com](https://platform.openai.com/), navigate to the **API keys** section, and click **Create new secret key**.
2. **Tavily API Key (Free)**: Go to [tavily.com](https://tavily.com/), sign up for a developer account, and obtain a free API key on your dashboard (includes 1,000 free search queries per month).

---

## 💻 Running the Application

To run the complete application, you will need two separate terminal windows (with your virtual environment activated in both):

### Terminal 1: Start the FastAPI Backend
```bash
uvicorn app.main:app --reload --port 8000
```
*The interactive API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).*

### Terminal 2: Start the Streamlit Chat UI
```bash
streamlit run ui/chat_app.py
```
*Streamlit will automatically open your web browser to [http://localhost:8501](http://localhost:8501).*

---

## 🧪 Testing the Application

We have included an automated test script (`test_app.py`) to verify the backend routes. 

Make sure the FastAPI backend is running in Terminal 1, then execute:
```bash
python test_app.py
```
**This script tests:**
1. **`GET /health`**: Verifies that the server returns a successful status.
2. **`POST /chat`**: Verifies that the ChatOpenAI agent responds to general questions.
3. **`POST /ingest`**: Generates a valid 1-page PDF file on-the-fly, uploads it, verifies chunk indexing, and cleans up.

---

## 💬 5 Suggested Test Queries to Try in the UI

Once the FastAPI backend and Streamlit UI are both running, try these queries in the chat box to test the agent's capabilities:

1. **General Research Question (Tests LLM capability)**
   > *"Summarize the current scientific understanding of quantum computing and explain superposition simply."*

2. **Academic Reference Search (Tests `arxiv_search` tool)**
   > *"What are the most cited arXiv papers on fine-tuning large language models in medicine?"*

3. **Follow-Up Session Inquiry (Tests `ConversationBufferWindowMemory` history)**
   > *"Great, summarize the abstract of the second paper you listed in our previous turn."*
   *(Make sure to send this right after your arXiv search to see the memory in action!)*

4. **Document Analysis (Tests `pdf_search` tool)**
   > *"According to my uploaded test_paper.pdf, what is the main research topic of the paper?"*
   *(Try this after uploading a PDF in the sidebar!)*

5. **Market/News Analysis (Tests `web_search` tool)**
   > *"What are the latest breakthrough announcements and consumer trends in generative AI from the past month?"*
