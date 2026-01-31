# DetFuzz

**DetFuzz: A Semantic-Guided Fuzzing Framework via Operation Logic Inference for Black-box IoT Devices**

- [Usage](#Usage)
- [Project Structure](##Project-Structure)

---

## Usage

### Step 1: Generate POC Scripts

```bash
python main.py
```

Analyzes input data, infers operation logic, and generates POC scripts to `{Vendor}/{Product}/output/`.

### Step 2: Execute POC and Verify Vulnerabilities

```bash
python executor.py
```

Executes generated POC scripts against the target device. Successful POCs are saved to `{Vendor}/{Product}/success/`.

---

## Project-Structure

```bash
DetFuzz/
├── main.py                 # Entry point for POC generation
├── inputs.py               # Load input data and environment config
├── analyzer.py             # LLM-based function classification and operation type inference
├── payload_producer.py     # Payload generation with cue-guided mutation
├── mutation.py             # Cue mutation and semantic similarity calculation
├── output_writer.py        # Write POC scripts to output directory
├── executor.py             # Execute POCs and verify vulnerabilities
├── database.json           # Function category knowledge base
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (API keys)
│
├── prompt/                 # LLM prompt templates
│   ├── target_choosing.md  # Target parameter selection prompt
│   ├── prerequisites.md    # Prerequisites analysis prompt
│   └── poc/                # POC script templates
│       ├── Tenda.py
│       └── TOTOLINK.py
│
└── {Vendor}/{Product}/     # Target device directory (e.g., Tenda/AC18/)
    ├── input/              # Input files (data packets + frontend code)
    ├── output/             # Generated POC scripts
    └── success/            # Verified successful POCs
```
