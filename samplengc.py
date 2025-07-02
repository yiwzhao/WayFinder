from openai import OpenAI

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "nvapi-....."
)

completion = client.chat.completions.create(
  model="deepseek-ai/deepseek-r1-distill-llama-8b",
  messages=[{"role":"user","content":" what is the capital of USA"}],
  temperature=0.6,
  top_p=0.7,
  max_tokens=4096,
  stream=True
)

for chunk in completion:
  if chunk.choices[0].delta.content is not None:
    print(chunk.choices[0].delta.content, end="")



