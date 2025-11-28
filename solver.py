from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import base64
import re
import requests
import os
from urllib.parse import urljoin, urlparse, parse_qs
from PyPDF2 import PdfReader
from io import BytesIO
import openai
import hashlib
import pandas as pd
import whisper
from aipipe import AIPipe

def get_answer_from_llm(quiz_content):
    """
    Uses a Large Language Model to interpret the quiz content and extract the answer.
    It will try OpenAI first, and if that fails, it will fall back to AI Pipe.
    """
    # Attempt to use OpenAI first
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if openai_api_key:
        try:
            openai.api_key = openai_api_key
            system_prompt = "You are an expert quiz solver. Your task is to analyze the given text and provide only the final answer to the question asked. Do not include any explanations, greetings, or additional text."

            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": quiz_content}
                ],
                temperature=0,
            )

            answer = response.choices[0].message.content.strip()
            print(f"LLM (OpenAI) generated answer: {answer}")

            try:
                return int(answer)
            except ValueError:
                try:
                    return float(answer)
                except ValueError:
                    return answer

        except Exception as e:
            print(f"OpenAI API call failed: {e}. Falling back to AI Pipe.")

    # Fallback to AI Pipe
    aipipe_api_key = os.environ.get("AIPIPE_API_KEY")
    if aipipe_api_key:
        try:
            pipe = AIPipe(aipipe_api_key)
            response = pipe.chat.completions.create(
                model="meta-llama/Llama-2-7b-chat-hf",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": quiz_content}
                ]
            )

            answer = response.choices[0].message.content.strip()
            print(f"LLM (AI Pipe) generated answer: {answer}")

            try:
                return int(answer)
            except ValueError:
                try:
                    return float(answer)
                except ValueError:
                    return answer

        except Exception as e:
            print(f"AI Pipe API call failed: {e}")
            return None

    print("Error: No valid API key found for either OpenAI or AI Pipe.")
    return None

def download_file(url, download_path='.'):
    """Downloads a file from a URL to a local path."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        content_disposition = response.headers.get('content-disposition')
        if content_disposition:
            filename = re.findall('filename="?([^"]+)"?', content_disposition)[0]
        else:
            filename = url.split('/')[-1]

        filepath = os.path.join(download_path, filename)

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"File downloaded to {filepath}")
        return filepath
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {e}")
        return None

def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF file."""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return None

def process_csv_file(csv_path):
    """Reads a CSV file and returns a summary for the LLM."""
    try:
        df = pd.read_csv(csv_path)
        return f"CSV Summary:\nColumns: {', '.join(df.columns)}\nFirst 5 rows:\n{df.head().to_string()}"
    except Exception as e:
        print(f"Error processing CSV file: {e}")
        return None

def transcribe_audio_file(audio_path):
    """Transcribes an audio file using OpenAI's Whisper model."""
    try:
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        return result["text"]
    except Exception as e:
        print(f"Error transcribing audio file: {e}")
        return None

def solve_alphametic_quiz(email):
    """
    Solves the alphametic quiz by reimplementing the JavaScript logic in Python.
    """
    sha1 = hashlib.sha1(email.encode('utf-8')).hexdigest()
    email_number = int(sha1[:4], 16)
    key = (email_number * 7919 + 12345) % 100000000
    key_str = str(key).zfill(8)
    return key_str

def solve_quiz(quiz_url):
    """
    This function takes a quiz URL, uses a headless browser to visit it,
    parses the content, and attempts to solve the quiz.
    It returns both the raw content and a BeautifulSoup object.
    """
    print(f"Solving quiz at: {quiz_url}")

    parsed_url = urlparse(quiz_url)
    if parsed_url.path == '/demo2':
        query_params = parse_qs(parsed_url.query)
        email = query_params.get('email', [None])[0]
        if email:
            print("Detected alphametic quiz. Solving directly.")
            key = solve_alphametic_quiz(email)
            return f"The calculated key is {key}. Submit this as the answer.", BeautifulSoup("<html></html>", "html.parser")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(quiz_url)
        page_source = driver.page_source
        driver.quit()
    except Exception as e:
        print(f"Error with Selenium: {e}")
        return None, None

    soup = BeautifulSoup(page_source, 'html.parser')

    script_tag = soup.find('script')
    raw_content = ""
    if script_tag and script_tag.string:
        match = re.search(r'atob\(`([^`]+)`\)', script_tag.string)
        if match:
            encoded_content = match.group(1).replace('\\n', '')
            try:
                decoded_content = base64.b64decode(encoded_content).decode('utf-8')
                raw_content = decoded_content
            except Exception as e:
                print(f"Error decoding base64 content: {e}")

    if not raw_content:
        raw_content = soup.get_text()

    return raw_content, soup

def submit_answer(email, secret, quiz_url, answer, submit_url):
    """
    Submits the answer to the specified URL.
    """
    payload = {
        "email": email,
        "secret": secret,
        "url": quiz_url,
        "answer": answer
    }

    try:
        response = requests.post(submit_url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error submitting answer: {e}")
        return None
