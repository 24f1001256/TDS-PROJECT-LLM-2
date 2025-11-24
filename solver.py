from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import base64
import re
import requests
import os
from urllib.parse import urljoin
from PyPDF2 import PdfReader
from io import BytesIO
import openai

# Set the OpenAI API key from an environment variable
openai.api_key = os.environ.get("OPENAI_API_KEY")

def get_answer_from_llm(quiz_content):
    """
    Uses a Large Language Model to interpret the quiz content and extract the answer.
    """
    if not openai.api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        return None

    try:
        # This prompt is designed to get a concise answer from the LLM.
        system_prompt = "You are an expert quiz solver. Your task is to analyze the given text and provide only the final answer to the question asked. Do not include any explanations, greetings, or additional text. For example, if the question is 'What is the sum of the value column?', and the answer is 12345, your response should be just '12345'."

        response = openai.chat.completions.create(
            model="gpt-4",  # A powerful model suitable for this task
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": quiz_content}
            ],
            temperature=0,  # Set to 0 for deterministic and consistent output
        )

        answer = response.choices[0].message.content.strip()
        print(f"LLM-generated answer: {answer}")

        # The answer might be a number, so we try to convert it.
        try:
            return int(answer)
        except ValueError:
            try:
                return float(answer)
            except ValueError:
                return answer  # Return as a string if it's not a number

    except Exception as e:
        print(f"An error occurred while calling the OpenAI API: {e}")
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

def solve_quiz(quiz_url):
    """
    This function takes a quiz URL, uses a headless browser to visit it,
    parses the content, and attempts to solve the quiz.
    It returns both the raw content and a BeautifulSoup object.
    """
    print(f"Solving quiz at: {quiz_url}")

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

    # If the base64 pattern is not found, use the plain text of the page.
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
