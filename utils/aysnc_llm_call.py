import os
import asyncio
import aiolimiter
import openai
import logging

from tqdm.asyncio import tqdm_asyncio, tqdm
from typing import Any, List, Dict

openai.api_key = os.environ["OPENAI_API_KEY"]
openai.organization = os.environ.get("OPENAI_ORGANIZATION")

async def _throttled_openai_chat_completion_acreate(
        client: openai.AsyncOpenAI,
        limiter: aiolimiter.AsyncLimiter,
        model: str,
        query: Dict[str, Any],
        temperature: float=0,
        top_p: float=1.0,
) -> Dict[str, Any]:
    message = query['messages']
    async with limiter:
        for _ in range(10):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=message,
                    n=1,
                    temperature=temperature,
                    top_p=top_p,
                    seed=1
                )
                query['model_output'] = response.choices[0].message.content

                return query
            except openai.RateLimitError:
                logging.warning("OpenAI API rate limit exceeded. Sleeping for 10 seconds.")
                await asyncio.sleep(10)

            except Exception as e2:
                error_type = type(e2)
                logging.warning(f"Error-{error_type}: {e2}")
                query['model_output'] = f"Error-{error_type}: {e2}"
                break

        return query


async def generate_from_openai_chat_completion(
    client: openai.AsyncOpenAI,
    limiter: aiolimiter.AsyncLimiter,
    queries: List[Dict[str, Any]],
    model: str,
    temperature: float,
    top_p: float,
) -> List[Dict[str, Any]]:
    """Generate from OpenAI Chat Completion API.
    Args:
        
    Returns:
        List of generated responses.
    """
    async_responses = [
        _throttled_openai_chat_completion_acreate(
            client=client,
            limiter=limiter,
            model=model,
            query=one_query,
            temperature=temperature,
            top_p=top_p
        )
        for one_query in queries
    ]

    responses = await tqdm_asyncio.gather(*async_responses)
    
    return responses

client = openai.AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# _prompt = "Tell me what 100 + {} equals to: "

# payload = []

# for i in range(10):
#     messages = [{"role": "user", "content": _prompt.format(i)}]
#     example = {
#         "messages": messages
#     }
#     payload.append(example)
    

# Set the # of request per minute
# REQUEST_PER_MINUTE = 60
# limiter = aiolimiter.AsyncLimiter(REQUEST_PER_MINUTE)

# result = asyncio.run(
#             generate_from_openai_chat_completion(
#                 client=client,
#                 limiter=limiter,
#                 queries=payload,
#                 model="gpt-4o",
#                 top_p=0.01,
#                 temperature=0
#             )
#         )

def process_llm_batch_calls(payload):
    """
    Process a single query through the OpenAI chat completion API.
    
    Args:
        example: A dictionary containing the 'messages' key with the message content
                Example: {'messages': [{'role': 'user', 'content': 'Tell me what 100 + 5 equals to: '}]}
    
    Returns:
        Dictionary with the original query and model output added
    """
    # Create payload with the single example
    # payload = []
    # for messages in list_of_messages:
    #     example = {
    #         "messages": [{"role": "user", "content": messages}]

    #     }
    #     payload.append(example)


    # Set rate limiter (can be adjusted based on your API limits)
    REQUEST_PER_MINUTE = 100
    limiter = aiolimiter.AsyncLimiter(REQUEST_PER_MINUTE)
    
    # Initialize the OpenAI client
    client = openai.AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Run the async function and get results
    result = asyncio.run(
        generate_from_openai_chat_completion(
            client=client,
            limiter=limiter,
            queries=payload,
            model="gpt-4o",
            top_p=0.01,
            temperature=0
        )
    )
    
    # Return the first (and only) result
    return result

# Example usage:
# example = {
#     "messages": [{"role": "user", "content": "Tell me what 100 + 5 equals to: "}]
# }
# response = process_llm_query(example)
# print(response['model_output'])