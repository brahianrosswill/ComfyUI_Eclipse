# ⚠️ Important Security Notice — Running LLMs Locally with ComfyUI

**Please read before using any Smart LM / LLM node that loads models from
Hugging Face or other public hubs via Python libraries.**

---

## TL;DR

If you load a model from a public hub using `transformers`, `torch.load`,
`pickle`, `joblib`, or any "convenience" LLM Python wrapper, **you are
running whatever code the model author put in that file** — on the same
user account that has access to your files, browser cookies, SSH keys,
crypto wallets, and ComfyUI workflows.

The safe answer for everyday use is:

> **Install Docker and run your LLM behind Ollama. Talk to it over HTTP
> from ComfyUI. Never load untrusted weights directly in the same Python
> process as ComfyUI.**

Eclipse's Smart LM Loader supports four Docker backends — **Ollama is
recommended for most users** because it is the only one that is safe on
*two* independent layers (see the three-tier comparison below).

---

## Why this matters — documented attacks (not theoretical)

These are real, public, dated incidents. None of this is speculation.

### 1. Malicious pickle models on Hugging Face — JFrog, Feb 2024
JFrog Security Research identified **~100 malicious models on Hugging Face**
containing real harmful payloads. The most notable case (`baller423/goober2`)
embedded a reverse shell via `pickle.__reduce__` that connected to a
hard-coded IP on `torch.load()`. The model card looked normal. Hugging Face
flagged it as "unsafe" but **did not block the download.**
Source: <https://jfrog.com/blog/data-scientists-targeted-by-malicious-hugging-face-ml-models-with-silent-backdoor/>

### 2. "nullifAI" — pickle scanner bypass, ReversingLabs, Feb 2025
Two HF models bypassed the Picklescan / HF malware scan by using a broken
pickle stream — the scanner errored out before reaching the malicious
opcode, but `torch.load()` still executed it. Real reverse shells were
delivered this way.
Source: <https://www.reversinglabs.com/blog/rl-identifies-malware-ml-model-hosted-on-hugging-face>

### 3. CVE-2023-6730 — `transformers` RCE via trusted-model loading
A *transitive* attack: loading a perfectly innocuous model could pull in a
second model (its tokenizer / dependency) that contained code execution.
The user only consciously downloaded one model.
Source: <https://nvd.nist.gov/vuln/detail/CVE-2023-6730>

### 4. PyPI / npm typosquatting targeting AI devs
Multiple campaigns through 2024–2025 published packages with names like
`openai-python`, `huggingface-cli`, `tensorflow-gpu-utils`, etc. that
exfiltrate `~/.aws/credentials`, `~/.ssh/`, browser cookies, Discord tokens,
and crypto wallets the moment they are `pip install`-ed.

### 5. Hugging Face's own warning
HF marks pickle / `.bin` / `.pt` files as **unsafe** for a reason. They
publicly recommend `.safetensors` for weights, but **safetensors only protect
the weights — they do not protect arbitrary code in `modeling_*.py`,
`configuration_*.py`, `*.py` files in the repo, or `trust_remote_code=True`
flags.** Many popular LLMs require `trust_remote_code=True` to run — and
that flag means "run whatever `.py` files come with the repo, no questions."

---

## What "running an LLM via the Python lib" actually means

When you do this in your ComfyUI process:

```python
AutoModelForCausalLM.from_pretrained("SomeAuthor/CoolNewLLM",
                                     trust_remote_code=True)
```

…you have just:

1. Downloaded `.py` files from a stranger's repo.
2. **Executed** those `.py` files inside the same Python interpreter that
   has full access to your `$HOME`, your saved API keys, your ComfyUI user
   folder, and (on most setups) your entire user account.
3. Loaded a pickle / unsafe tensor file that may itself execute code on load.

There is no sandbox. There is no permission prompt. There is no
"are you sure?" — exactly as if you had downloaded and double-clicked a
`.exe`.

---

## The three-tier security ladder

All four Docker backends are dramatically safer than in-process
`transformers`, but they are not equal. The ladder from worst to best:

### 🔴 Worst — `transformers` directly in the ComfyUI Python process
- Loads pickle / `.bin` weights → **RCE on load.**
- `trust_remote_code=True` runs strangers' `.py` files **in-process.**
- Full access to your `$HOME`, SSH keys, browser cookies, wallets,
  ComfyUI workflows, Civitai / HF API tokens.
- One bad model = one compromised user account.

### 🟡 Better — vLLM / SGLang / llama.cpp-HTTP in Docker
- Still pulls models from the open Hugging Face registry.
- Still loads PyTorch `.bin` (pickle) weights when present.
- Still honors `--trust-remote-code` if you (or a default config) set it.
- **BUT** — the exploit now runs *inside the container*, not on your host.
  - No access to your home directory, keys, wallets, or workflows.
  - `docker rm -f <name>` wipes it clean in one command.
  - Network egress can be firewalled per-container.
- **Safe usage rule:** stick to `.safetensors` weights and never pass
  `--trust-remote-code` unless you've read every `.py` file in the repo.

### 🟢 Best for casual users — Ollama in Docker
Ollama is the strictest of the four because it is defense-in-depth on
**two independent layers**:

#### Layer 1 — Format: GGUF only
Ollama can only load **GGUF** files. GGUF is a plain tensor container
(similar in spirit to `.safetensors`):
- No `pickle` opcodes.
- No `__reduce__` trick.
- No embedded `.py` files.
- No `trust_remote_code` execution path.

Even a **deliberately malicious GGUF** cannot run code on load. The worst
it can do is produce bad outputs (gibberish, jailbreak attempts, bias).
That's a content problem, not a security problem.

#### Layer 2 — Registry: `ollama.com/library` is curated, not open upload
This is the part most people miss:

- **Hugging Face** = open upload. Anyone makes an account and uploads
  anything — including `baller423/goober2`. JFrog found ~100 malicious
  models there.
- **Ollama's official library** at <https://ollama.com/library> is
  maintained by the Ollama team. The popular tags (`llama3.2`,
  `qwen2.5`, `mistral`, `gemma3`, `deepseek-r1`, `phi4`, …) are **official
  builds packaged by Ollama itself** from the original lab weights.
- Users *can* push to their own namespace (`user/mymodel`), but those are
  clearly separated under a username prefix — same way Docker Hub
  separates `nginx` (official) from `someuser/nginx` (third-party).

When you do `ollama pull qwen2.5:14b`, you're pulling from the same kind
of trust source you'd use running the official `nginx` Docker image — not
from a random uploader.

(Pulling `ollama pull someuser/sketchy-model` is back to "trust a stranger"
territory, but it is **still only GGUF**, so still no code execution path.)

---

## Combined threat matrix

| Threat                                     | `transformers` (host) | vLLM / SGLang (Docker)  | Ollama (Docker)    |
| ------------------------------------------ | :-------------------: | :---------------------: | :----------------: |
| Code exec on model load                    | 🔴 yes (pickle)       | 🟡 yes, but contained   | 🟢 impossible      |
| `trust_remote_code` runs strangers' Python | 🔴 yes (in-process)   | 🟡 yes, but contained   | 🟢 not supported   |
| Anyone can publish a model                 | 🔴 yes (HF open)      | 🔴 yes (HF open)        | 🟢 curated library |
| Damage reaches your `$HOME` / keys         | 🔴 yes                | 🟢 no                   | 🟢 no              |
| Easy to wipe and start clean               | 🟠 manual             | 🟢 `docker rm`          | 🟢 `docker rm`     |
| Inference speed (consumer GPU)             | 🟡 OK                 | 🟢 fastest at scale     | 🟢 fastest casual  |
| Model catalog                              | 🟢 huge               | 🟢 huge                 | 🟢 huge            |
| One-time setup                             | 🟢 minutes            | 🟡 ~30 min              | 🟡 ~30 min         |

**Spend the 30 minutes once. Your future self will thank you.**

---

## The recommended setup: Docker + Ollama

Eclipse ships with full Docker install guides — please follow them instead
of guessing your way through it:

- **Linux:** [`Readme/Docker_Installation_Guide_Linux.md`](../Readme/Docker_Installation_Guide_Linux.md)
- **Windows / macOS:** [`Readme/Docker_Installation_Guide.md`](../Readme/Docker_Installation_Guide.md)

Both guides cover Docker engine setup, NVIDIA GPU passthrough, and starting
the Ollama / vLLM / SGLang / llama.cpp containers that Eclipse's Smart LM
Loader talks to.

### Then in ComfyUI

Use the **Smart LM Loader [Eclipse]** node, set the backend to **Ollama**,
point it at `http://localhost:11434/v1`, and select your pulled model. Done.

---

## "But I trust this one model from this one author"

That's fine — but please at least:

1. Prefer `.safetensors` weights. Refuse `.bin` / `.pt` / `.pkl` from
   unknown authors.
2. Avoid `trust_remote_code=True` unless the repo is a major lab
   (Meta, Qwen, Google, Mistral, Microsoft) **and** you read the `.py`
   files. Yes, actually read them.
3. Even then: prefer running via Ollama / vLLM / SGLang / llama.cpp in
   Docker. Almost every popular open model has a GGUF / Ollama version
   within days of release.
4. If you must run a model in-process, do it in a throwaway VM or a
   dedicated user account with no access to your real files / keys.

---

### Sources

- JFrog — *Data Scientists Targeted by Malicious Hugging Face ML Models with
  Silent Backdoor* (Feb 27, 2024)
  <https://jfrog.com/blog/data-scientists-targeted-by-malicious-hugging-face-ml-models-with-silent-backdoor/>
- ReversingLabs — *nullifAI: malicious ML models bypassing Picklescan*
  (Feb 2025)
  <https://www.reversinglabs.com/blog/rl-identifies-malware-ml-model-hosted-on-hugging-face>
- NIST — CVE-2023-6730 (transformers transitive RCE)
  <https://nvd.nist.gov/vuln/detail/CVE-2023-6730>
- Hugging Face — *Pickle scanning & security* docs
  <https://huggingface.co/docs/hub/en/security-pickle>
- Hugging Face — *safetensors*
  <https://github.com/huggingface/safetensors>
- Ollama — official model library
  <https://ollama.com/library>
- GGUF format spec
  <https://github.com/ggerganov/ggml/blob/master/docs/gguf.md>
- HiddenLayer — *Weaponizing ML models with ransomware*
  <https://hiddenlayer.com/research/weaponizing-machine-learning-models-with-ransomware/>
