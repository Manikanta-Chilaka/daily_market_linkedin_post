import os
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup

from dotenv import load_dotenv

load_dotenv()

# Configuration
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')
EMAIL_TO = os.getenv('EMAIL_TO')


def get_market_context():
    """
    Scrape news headlines to infer current market sentiment.
    Alternatively, you can use news APIs (e.g., NewsAPI, Finnhub).
    """
    try:
        url = "https://www.moneycontrol.com/news/business/markets/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        headlines = []
        for item in soup.select('li.clearfix')[:10]:
            headline = item.text.strip()
            if headline:
                headlines.append(headline)

        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'headlines': headlines
        }

    except Exception as e:
        print(f"Error scraping market context: {e}")
        return None


def generate_advisory_post(context):
    """Generate advisory post using OpenAI based on current market sentiment"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_KEY'))

        headlines_text = "\n".join(context['headlines'])

        prompt = f"""
You are a SEBI-registered investment advisor with 20 years of experience, using NISM Series Investment Advisor Level 1 & 2 principles.

Your job is to create a LinkedIn post (max 280 words) based on the current Indian market sentiment. Use the following news headlines from the last 7–30 days to determine the most relevant financial concern for 30–50 year old corporate employees with families in India:

HEADLINES:
{headlines_text}

Based on these headlines, select ONE of the following themes:
- Volatility/SIP/Long-term investing
- Profit booking/Portfolio rebalancing
- Debt/EMI/Asset allocation
- Inflation/Gold/Real estate
- Global diversification/Currency risk/Safe havens

Create a LinkedIn post that:
- Hooks with a shocking stat or reality
- Tells an anonymized emotional client story
- Explains the chosen concept simply
- Provides 3 actionable tips
- Ends with a reflective question
- Uses 1–3 emojis
- Includes SEBI compliance language

Avoid jargon. Be relatable, professional, and compliance-aware.
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"Error generating post: {e}")
        return None


def send_email(content, max_retries=3, retry_delay=5):
    """
    Enhanced email sending with:
    - Multiple retries
    - Error logging
    - Fallback saving to file
    """
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"LinkedIn Advisory Post - {datetime.now().strftime('%d %b %Y')}"
    msg.attach(MIMEText(content, 'plain'))

    last_exception = None

    for attempt in range(max_retries):
        try:
            # Try SSL first
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
                server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                server.send_message(msg)
                print("✓ Email sent successfully via SSL")
                return True

        except Exception as e:
            last_exception = e
            print(f"Attempt {attempt + 1} failed: {type(e).__name__}")

            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

    # If all retries failed
    error_details = {
        'timestamp': str(datetime.now()),
        'error': str(last_exception),
        'content': content,
        'subject': msg['Subject']
    }

    save_failed_post(error_details)
    return False


def save_failed_post(error_details):
    """Save failed posts to a JSON file for manual recovery"""
    try:
        failures_dir = Path("failed_posts")
        failures_dir.mkdir(exist_ok=True)

        filename = failures_dir / f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w') as f:
            json.dump(error_details, f, indent=2)

        print(f"⚠ Saved failed post to {filename}")

    except Exception as e:
        print(f"Failed to save error log: {e}")


if __name__ == "__main__":
    print("Fetching market context...")
    market_context = get_market_context()

    if market_context:
        print("Generating advisory post...")
        post = generate_advisory_post(market_context)

        if post:
            print("\n" + "=" * 50)
            print(post)
            print("=" * 50 + "\n")

            if not send_email(post):
                print("\n❌ All retries failed. Post saved to 'failed_posts' folder.")
                print("You can manually send it later using:")
                print(f"Subject: {market_context['date']} LinkedIn Advisory Post")