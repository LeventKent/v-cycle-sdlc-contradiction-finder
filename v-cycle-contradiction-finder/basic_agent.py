import os
from aws_bedrock_token_generator import provide_token
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel

region = os.environ["AWS_REGION"]
base_url = os.environ["OPENAI_BASE_URL"]
model_id = os.environ["MODEL_ID"]

print(f"  Region:   {region}")
print(f"  Base URL: {base_url}")
print(f"  Model:    {model_id}")

model = OpenAIResponsesModel(
    model_id=model_id,
    client_args={
        "api_key": provide_token(region=region),
        "base_url": base_url,
    },
    stateful=True
)

agent = Agent(model=model)
response = agent("What is the value of Amazon share price in dollars? Check internet if needed.")

response = agent("What did I ask you before? What steps did you take to answer it?")
