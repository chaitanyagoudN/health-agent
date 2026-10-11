from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()

response = client.responses.create(
    model="gpt-5.6",
    input="Say exactly: Health Chart Agent API connection is working."
)

print(response.output_text)