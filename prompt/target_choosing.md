You are a senior IoT fuzzing expert. Please generate test payloads based on the inputs below:

- **Operation Type**: `{operation_type}`
- **Function Category**: `{function_category}`
- **DATA Packet**: `{DATA_PACKET}`
- **Cue Parameters**: `{cues}`

## Step 1. Vulnerability Type

Based on information above, infer the most likely vulnerability type:

- **set** — Likely to trigger **buffer overflow** (the most common IoT vulnerability). Focus on the text input configuration fields (e.g., list).
- **exec** —Likely to trigger **command injection**. Focus on parameters that may be passed to system (e.g., destination addresses, command arguments).
- **set&exec** — Test **both** classes.

## Step 2. Mutate Target Selection

Identify the **most likely vulnerable parameters** to mutate in the `{DATA_PACKET}`:

1. **Prioritization**: Identify all parameters in the packet and prioritize those related to `{cues}` and most likely to contain vulnerabilities.
2. **Selection Count Limit**: Select **at most 5** parameters in total. If there are more than 5 candidates, only keep the top 5 most likely vulnerable ones.
3. **Placeholder**: Parameters potential with command injection: replace its value with placeholder `{cmdi}`; Potential with buffer overflow: replace with placeholder `{overflow}`.

**Important**:
- Each item in the output MUST correspond to **one** mutated parameter.
- The total number of items (mutated parameters) MUST NOT exceed **5**.
- Never use actual attack strings (e.g., "AAAA..." or shell commands); use placeholders only.

Return **only** a strict, single JSON object (no extra text outside the JSON).

## Output Schema

```json
{
  "items": [
    { "type": "overflow", "target": "k1={overflow}"},
    { "type": "cmdi", "target": "k3={cmdi}"}
    // Up to **5** distinct items in total
  ]
}
```
