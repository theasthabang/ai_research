import os
import requests
import sys

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

BASE_URL = "http://localhost:8000"


def create_dummy_pdf(filename="test_paper.pdf"):
    """
    Generates a syntactically valid minimal 1-page PDF containing a research statement.
    This enables self-contained testing of the PDF ingestion route without external assets.
    """
    pdf_content = (
        "%PDF-1.4\n"
        "1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        "2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
        "3 0 obj <</Type /Page /Parent 2 0 R /Resources <</Font <</F1 4 0 R>>>> /MediaBox [0 0 612 792] /Contents 5 0 R>> endobj\n"
        "4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
        "5 0 obj <</Length 56>> stream\n"
        "BT\n"
        "/F1 12 Tf\n"
        "72 712 Td\n"
        "(This is a test research paper on Artificial Intelligence.) Tj\n"
        "ET\n"
        "endstream\n"
        "endobj\n"
        "xref\n"
        "0 6\n"
        "0000000000 65535 f\n"
        "0000000009 00000 n\n"
        "0000000056 00000 n\n"
        "0000000111 00000 n\n"
        "0000000212 00000 n\n"
        "0000000282 00000 n\n"
        "trailer <</Size 6 /Root 1 0 R>>\n"
        "startxref\n"
        "389\n"
        "%%EOF\n"
    )
    with open(filename, "wb") as f:
        f.write(pdf_content.encode("ascii"))
    print(f"Created temporary file: '{filename}'")


def run_tests():
    # 0. Check if backend is running
    try:
        requests.get(f"{BASE_URL}/health")
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: FastAPI backend is not running at http://localhost:8000")
        print("Please start the backend first by running:")
        print("  uvicorn app.main:app --reload --port 8000")
        sys.exit(1)

    print("\n🚀 Starting AI Research Helper tests...\n" + "=" * 40)

    # Test 1: GET /health
    print("\nRunning Test 1: GET /health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.json() == {"status": "ok"}, f"Expected {{'status': 'ok'}}, got {response.json()}"
        print("✅ Test 1 Passed: Backend health check successful!")
    except Exception as e:
        print(f"❌ Test 1 Failed: {e}")

    # Test 2: POST /chat
    print("\nRunning Test 2: POST /chat session query...")
    try:
        payload = {
            "query": "What is machine learning?",
            "session_id": "test-suite-session-id"
        }
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=60.0)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "answer" in data, "Response body missing 'answer' key"
        assert "sources" in data, "Response body missing 'sources' key"
        assert "confidence" in data, "Response body missing 'confidence' key"
        assert "score" in data["confidence"], "Confidence metadata missing 'score' key"
        assert "reason" in data["confidence"], "Confidence metadata missing 'reason' key"
        
        print(f"✅ Test 2 Passed: Chat agent successfully responded with confidence {data['confidence']['score']}/10!")
        print(f"   Reason: {data['confidence']['reason']}")
        print(f"   Response Preview: {data['answer'][:150]}...")
    except Exception as e:
        print(f"❌ Test 2 Failed: {e}")

    # Test 3: POST /ingest
    print("\nRunning Test 3: POST /ingest file upload...")
    temp_pdf = "sample_test_paper.pdf"
    create_dummy_pdf(temp_pdf)
    
    try:
        with open(temp_pdf, "rb") as f:
            files = {"file": (temp_pdf, f, "application/pdf")}
            response = requests.post(f"{BASE_URL}/ingest", files=files, timeout=30.0)
            
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "success", f"Expected status 'success', got {data.get('status')}"
        chunks = data.get("chunks_added", 0)
        assert chunks > 0, f"Expected chunks_added > 0, got {chunks}"
        print(f"✅ Test 3 Passed: PDF uploaded and ingested successfully! (Added {chunks} chunks)")

        # Test 4: POST /mindmap
        print("\nRunning Test 4: POST /mindmap generation...")
        mm_payload = {
            "filename": temp_pdf,
            "topic": "Artificial Intelligence"
        }
        response = requests.post(f"{BASE_URL}/mindmap", json=mm_payload, timeout=60.0)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        mm_data = response.json()
        assert "center" in mm_data, "Mindmap missing 'center' key"
        assert "branches" in mm_data, "Mindmap missing 'branches' key"
        print(f"✅ Test 4 Passed: Mindmap successfully generated for topic '{mm_data['center']}'!")

        # Test 5: POST /revision-notes
        print("\nRunning Test 5: POST /revision-notes generation...")
        rev_payload = {
            "filename": temp_pdf,
            "topic": "Artificial Intelligence"
        }
        response = requests.post(f"{BASE_URL}/revision-notes", json=rev_payload, timeout=90.0)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        rev_data = response.json()
        assert "topic" in rev_data, "Revision notes missing 'topic' key"
        assert "mindmap" in rev_data, "Revision notes missing 'mindmap' key"
        assert "crisp_notes" in rev_data, "Revision notes missing 'crisp_notes' key"
        assert "keywords" in rev_data, "Revision notes missing 'keywords' key"
        print(f"✅ Test 5 Passed: Revision notes successfully generated with {len(rev_data['crisp_notes'])} crisp notes!")

        # Test 6: POST /detailed-mindmap
        print("\nRunning Test 6: POST /detailed-mindmap generation...")
        response = requests.post(f"{BASE_URL}/detailed-mindmap", params={"filename": temp_pdf, "total_pages": 1}, timeout=120.0)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        det_data = response.json()
        assert "pages" in det_data, "Detailed mindmap missing 'pages'"
        assert "total" in det_data, "Detailed mindmap missing 'total'"
        print(f"✅ Test 6 Passed: Detailed mindmap successfully generated with {det_data['total']} page(s)!")

    except Exception as e:
        print(f"❌ Test Failed: {e}")
    finally:
        # Clean up temporary test files
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)
            print(f"Cleaned up temporary file: '{temp_pdf}'")

    print("\n" + "=" * 40 + "\n🎉 All tests completed!")


if __name__ == "__main__":
    run_tests()
