import os
import math
from typing import List

from dotenv import load_dotenv
from openai import OpenAI


def llm_mutation(function_category: str, uri: str, api_key, api_base, model, used_cues: List[str] = None, output_mode: str = "2") -> List[str]:
    """
    Generate new configuration-related clue parameters based on the functional category, excluding clues that have already been used.
    

    Returns:
        Newly generated list of clue parameters (max 5 items)
    """
    if used_cues is None: 
        used_cues = []
    
    system_msg = 'You are an IoT fuzz testing expert, specializing in analyzing configuration parameters of network devices. You excel at identifying the most core and critical configuration parameter names.'

    user_message = f'''
Please analyze the {uri} based on its functional category {function_category}. Identify the most essential and critical configuration parameter required for this type of functionality, and generate its likely parameter name.

## CRITICAL Requirements:

1. **Quantity**: Only one clue field should be returned.

2. **Core Configuration Focus**: Only consider the most essential and critical configuration-related clue within the function "{function_category}".

3. **Duplication Avoidance**: Ensure the generated clue is not in the already used list.

## Clues Already Used (MUST EXCLUDE):
{used_cues}

## Output Format:
Return ONLY a Python list with EXACTLY 1 item, named clue1. Do NOT include any explanation or extra text:
["clue1"]
'''
    

    client = OpenAI(api_key=api_key, base_url=api_base)
    
    if output_mode == "2":
        print(f"\n[LLM Call] Clue Mutation (llm_mutation)")
        print(f"model: {model}")
        print(f"System Message:")
        print("-" * 60)
        print(system_msg)
        print("-" * 60)
        print(f"User Message (Prompt):")
        print("-" * 60)
        print(user_message)
        print("-" * 60)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_message}
        ],
        temperature=0.3,  # Lower the temperature to improve consistency and quality.
        top_p=0.8,        # Lower top_p to reduce low-quality candidates
        max_tokens=100    # Limit output length to avoid generating excessive content
    )
    revised_text = response.choices[0].message.content.strip().replace('\n', '')
    
    if output_mode == "2":
        print(f"\noutput (Response):")
        print("-" * 60)
        print(revised_text)
        print("-" * 60)
    
    # Parse the returned list
    new_cues = []
    if revised_text.startswith("[") and revised_text.endswith("]"):
        try:
            new_cues = eval(revised_text)
            # Filter out used clues
            new_cues = [cue for cue in new_cues if cue not in used_cues]
            # Ensure the number of returned clues does not exceed 5
            new_cues = new_cues[:5]
            print(f"New clues: {new_cues}")
        except Exception as e:
            print(f"Failed to parse mutation results: {revised_text}, 错误: {e}")
    
    return new_cues


def _load_openai_config_for_similarity():
    load_dotenv(override=False)
    api_base = os.getenv("OPENAI_API_BASE_Eembedding")
    api_key = os.getenv("OPENAI_API_KEY_Eembedding")
    embedding_model = os.getenv("EMBEDDING_MODEL")

    return api_base, api_key, embedding_model


def _semantic_similarity_openai(text1: str, text2: str) -> float:

    api_base, api_key, embedding_model = _load_openai_config_for_similarity()

    try:
        client = OpenAI(api_key=api_key, base_url=api_base)
        resp = client.embeddings.create(
            model=embedding_model,
            input=[text1, text2],
        )
        if not resp.data or len(resp.data) < 2:
            return 0.0

        v1 = resp.data[0].embedding
        v2 = resp.data[1].embedding

        # Calculate Cosine Similarity
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        cos_sim = dot / (norm1 * norm2)
        
        score = (cos_sim + 1.0) / 2.0
        return max(0.0, min(1.0, float(score)))
    except Exception as e:
        print(f"Failed to calculate semantic similarity: {e}")
        return 0.0


def simple_fitness(clue: str, payload_str: str) -> float:
    """
    """
    # 
    clue_lower = clue.lower()
    payload_lower = payload_str.lower()

    # 
    if clue_lower in payload_lower or payload_lower in clue_lower:
        return 1.0

    # 
    def longest_common_substring(a: str, b: str) -> int:
        if not a or not b:
            return 0
        m, n = len(a), len(b)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        longest = 0
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                    if dp[i][j] > longest:
                        longest = dp[i][j]
        return longest

    lcs_len = longest_common_substring(clue_lower, payload_lower)
    max_len = max(len(clue_lower), len(payload_lower)) or 1
    string_sim = lcs_len / max_len

    # 
    if string_sim >= 0.6:
        score = string_sim
        return float(max(0.0, min(1.0, score)))

    # 
    sem_score = _semantic_similarity_openai(clue_lower, payload_lower)

    return float(max(0.0, min(1.0, max(string_sim, sem_score))))
