from flask import Flask, request, jsonify
import os
from solver import (
    solve_quiz,
    submit_answer,
    get_answer_from_llm,
    download_file,
    extract_text_from_pdf,
    process_csv_file,
    transcribe_audio_file
)
import threading
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

app = Flask(__name__)

# This should be replaced with the actual secret from the Google Form
SECRET_STRING = os.environ.get("SECRET_STRING", "default-secret")

def solve_and_submit(email, secret, quiz_url):
    """
    This function runs the quiz solving and submission process in a separate thread,
    and handles the quiz chain.
    """
    print(f"--- Solving quiz: {quiz_url} ---")

    # Add the email to the quiz URL if it's a demo2 link
    if "demo2" in quiz_url and "email=" not in quiz_url:
        quiz_url += f"?email={email}"

    raw_quiz_content, soup = solve_quiz(quiz_url)

    if not raw_quiz_content:
        print("Could not retrieve quiz content.")
        return

    print(f"Quiz content: {raw_quiz_content}")

    # Initialize the context for the LLM
    llm_context = raw_quiz_content

    # Check for download links in the quiz content
    download_link_match = re.search(r'Download <a href="([^"]+)">file</a>', raw_quiz_content)
    if download_link_match:
        download_url = download_link_match.group(1)

        if not download_url.startswith('http'):
            download_url = urljoin(quiz_url, download_url)

        print(f"Found download link: {download_url}")

        downloaded_file_path = download_file(download_url)

        if downloaded_file_path:
            file_extension = os.path.splitext(downloaded_file_path)[1].lower()
            file_content = ""

            if file_extension == '.pdf':
                file_content = extract_text_from_pdf(downloaded_file_path)
            elif file_extension == '.csv':
                file_content = process_csv_file(downloaded_file_path)
            elif file_extension in ['.wav', '.mp3', '.ogg']:
                file_content = transcribe_audio_file(downloaded_file_path)
            else:
                print(f"Unsupported file type: {file_extension}")

            if file_content:
                llm_context += f"\n\n--- Content from downloaded {file_extension} file ---\n" + file_content

    answer = get_answer_from_llm(llm_context)

    if answer is None:
        print("Could not get an answer from the LLM.")
        return

    submit_url = None
    submit_pre = soup.find('pre')
    if submit_pre:
        submit_url_match = re.search(r'Post your answer to (https?://[^\s/$.?#].[^\s]*)', submit_pre.get_text())
        if submit_url_match:
            submit_url = submit_url_match.group(1)

    if not submit_url:
        submit_url_match = re.search(r'(?:Post your answer to|submit to|submit at)\s+(https?://[^\s/$.?#].[^\s]*)', raw_quiz_content, re.IGNORECASE)
        if submit_url_match:
            submit_url = submit_url_match.group(1)

    # A special case for demo2, where the submit URL is provided in the instructions
    if "demo2" in quiz_url and "tackle /demo2-checksum" in raw_quiz_content:
        submit_url = urljoin(quiz_url, "/submit")


    if not submit_url:
        print("Could not find submit URL in the quiz content.")
        return

    print(f"Found submit URL: {submit_url}")

    submission_result = submit_answer(email, secret, quiz_url, answer, submit_url)

    if not submission_result:
        print("Submission failed.")
        return

    print(f"Submission result: {submission_result}")

    if submission_result.get("correct") and "url" in submission_result and submission_result["url"]:
        next_quiz_url = submission_result["url"]
        if not next_quiz_url.startswith('http'):
            next_quiz_url = urljoin(quiz_url, next_quiz_url)

        solve_and_submit(email, secret, next_quiz_url)
    else:
        print("--- Quiz chain finished or submission was incorrect. ---")


@app.route("/", methods=["POST"])
def handle_quiz_request():
    try:
        data = request.get_json()
    except:
        return jsonify({"error": "Invalid JSON"}), 400

    if not data or "secret" not in data or "email" not in data or "url" not in data:
        return jsonify({"error": "Missing required fields"}), 400

    if data["secret"] != SECRET_STRING:
        return jsonify({"error": "Invalid secret"}), 403

    thread = threading.Thread(target=solve_and_submit, args=(data["email"], data["secret"], data["url"]))
    thread.start()

    return jsonify({"status": "Quiz solving initiated"}), 200

@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
