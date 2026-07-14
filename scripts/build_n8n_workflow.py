import json
import os

with open('/Users/suleymanovasiman/Documents/personal-ai-agent/router-prompts/router-system-prompt.md') as f:
    router_prompt = f.read()
with open('/Users/suleymanovasiman/Documents/personal-ai-agent/router-prompts/local-model-system-prompt.md') as f:
    local_prompt = f.read()
with open('/Users/suleymanovasiman/Documents/personal-ai-agent/router-prompts/memory-extraction-prompt.md') as f:
    memextract_prompt = f.read()
with open('/Users/suleymanovasiman/Documents/personal-ai-agent/router-prompts/reminder-extraction-prompt.md') as f:
    reminder_extract_prompt = f.read()
with open('/Users/suleymanovasiman/Documents/personal-ai-agent/router-prompts/project-extraction-prompt.md') as f:
    project_extract_prompt = f.read()

POSTGRES_CRED = {"id": "ced8rY9xb6GUVTd7", "name": "Postgres (personal-ai-agent)"}

TELEGRAM_CRED = {"id": "WYAZd7eAoSGcEFFq", "name": "Telegram Bot (personal-ai-agent)"}
RUNPOD_CRED = {"id": "hVJihjnLX8OKvWIw", "name": "RunPod API"}
ROUTER_EP = "guadc1rxe929r4"
LOCAL_EP = "d902gj6z3zpe21"
EMBED_EP = "954od6235588eo"
MAX_ATTEMPTS = 90   # 90 * 10s = 15 min cold-start ceiling
WAIT_SECONDS = 10

def router_run_body():
    body = {
        "input": {
            "openai_route": "/v1/chat/completions",
            "openai_input": {
                "model": "Qwen/Qwen2.5-3B-Instruct",
                "messages": [
                    {"role": "system", "content": router_prompt},
                    {"role": "user", "content": "PLACEHOLDER"}
                ],
                "max_tokens": 200,
                "temperature": 0
            }
        }
    }
    return json.dumps(body).replace(
        '"PLACEHOLDER"',
        "{{ JSON.stringify(($json.historyText || '') + 'Current message: \"' + $json.cleanText + '\"') }}"
    )

def local_run_body():
    body = {
        "input": {
            "openai_route": "/v1/chat/completions",
            "openai_input": {
                "model": "Qwen/Qwen2.5-14B-Instruct",
                "messages": [
                    {"role": "system", "content": "SYSTEM_PLACEHOLDER"},
                    {"role": "user", "content": "PLACEHOLDER"}
                ],
                "max_tokens": 300,
                "temperature": 0
            }
        }
    }
    s = json.dumps(body).replace('"PLACEHOLDER"', '{{ JSON.stringify($json.cleanText) }}')
    s = s.replace('"SYSTEM_PLACEHOLDER"', '{{ JSON.stringify($json.localSystemPrompt) }}')
    return s

def embed_run_body():
    # Note: input content is filled via expression at call sites
    body = {"input": {"model": "intfloat/multilingual-e5-small", "input": "PLACEHOLDER"}}
    return json.dumps(body).replace('"PLACEHOLDER"', "{{ JSON.stringify('query: ' + $json.cleanText) }}")

def memextract_run_body():
    body = {
        "input": {
            "openai_route": "/v1/chat/completions",
            "openai_input": {
                "model": "Qwen/Qwen2.5-3B-Instruct",
                "messages": [
                    {"role": "system", "content": memextract_prompt},
                    {"role": "user", "content": "PLACEHOLDER"}
                ],
                "max_tokens": 100,
                "temperature": 0
            }
        }
    }
    return json.dumps(body).replace('"PLACEHOLDER"', '{{ JSON.stringify($json.memExtractInput) }}')

def memembed_run_body():
    body = {"input": {"model": "intfloat/multilingual-e5-small", "input": "PLACEHOLDER"}}
    return json.dumps(body).replace('"PLACEHOLDER"', "{{ JSON.stringify('passage: ' + $json.extractedFact) }}")

def reminder_extract_run_body():
    body = {
        "input": {
            "openai_route": "/v1/chat/completions",
            "openai_input": {
                "model": "Qwen/Qwen2.5-3B-Instruct",
                "messages": [
                    {"role": "system", "content": reminder_extract_prompt},
                    {"role": "user", "content": "PLACEHOLDER"}
                ],
                "max_tokens": 150,
                "temperature": 0
            }
        }
    }
    return json.dumps(body).replace('"PLACEHOLDER"', '{{ JSON.stringify($json.reminderExtractInput) }}')

def project_extract_run_body():
    body = {
        "input": {
            "openai_route": "/v1/chat/completions",
            "openai_input": {
                "model": "Qwen/Qwen2.5-3B-Instruct",
                "messages": [
                    {"role": "system", "content": project_extract_prompt},
                    {"role": "user", "content": "PLACEHOLDER"}
                ],
                "max_tokens": 200,
                "temperature": 0
            }
        }
    }
    return json.dumps(body).replace('"PLACEHOLDER"', '{{ JSON.stringify($json.projectExtractInput) }}')

nodes = []
connections = {}

def add_node(n):
    nodes.append(n)

def http_node(name, method, url, position, body=None, node_id=None):
    if '{{' in url and not url.startswith('='):
        url = '=' + url
    params = {
        "method": method,
        "url": url,
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "options": {"timeout": 30000}
    }
    if body is not None:
        params["sendBody"] = True
        params["specifyBody"] = "json"
        if '{{' in body and not body.startswith('='):
            body = '=' + body
        params["jsonBody"] = body
    return {
        "parameters": params,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": position,
        "name": name,
        "credentials": {"httpHeaderAuth": RUNPOD_CRED},
        "id": node_id or name
    }

def code_node(name, code, position, node_id=None):
    return {
        "parameters": {"jsCode": code},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "name": name,
        "id": node_id or name
    }

def wait_node(name, seconds, position, node_id=None):
    return {
        "parameters": {"amount": seconds, "unit": "seconds"},
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "position": position,
        "name": name,
        "webhookId": name.lower().replace(' ', '-').replace('?', ''),
        "id": node_id or name
    }

def if_node(name, left_expr, right_value, op_type, op, position, node_id=None):
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "typeValidation": "loose"},
                "conditions": [
                    {"id": f"{name}-cond", "leftValue": left_expr, "rightValue": right_value, "operator": {"type": op_type, "operation": op}}
                ],
                "combinator": "and"
            },
            "options": {}
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": position,
        "name": name,
        "id": node_id or name
    }

def telegram_node(name, chat_id_expr, text_expr, position, node_id=None):
    return {
        "parameters": {"chatId": chat_id_expr, "text": text_expr, "additionalFields": {"appendAttribution": False}},
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": position,
        "name": name,
        "credentials": {"telegramApi": TELEGRAM_CRED},
        "id": node_id or name
    }

def postgres_node(name, query, param_expr, position, node_id=None):
    return {
        "parameters": {
            "operation": "executeQuery",
            "query": query,
            "options": {"queryReplacement": param_expr}
        },
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.6,
        "position": position,
        "name": name,
        "credentials": {"postgres": POSTGRES_CRED},
        "id": node_id or name
    }

def connect(src, dst, src_out=0):
    connections.setdefault(src, {"main": []})
    while len(connections[src]["main"]) <= src_out:
        connections[src]["main"].append([])
    connections[src]["main"][src_out].append({"node": dst, "type": "main", "index": 0})

# ---- Static entry nodes ----
add_node({
    "parameters": {"updates": ["message"]},
    "type": "n8n-nodes-base.telegramTrigger",
    "typeVersion": 1.1,
    "position": [0, 0],
    "name": "Telegram Trigger",
    # Must be a real UUID, not a human-readable slug — n8n's webhook routing table
    # doesn't reliably register non-UUID ids (see docs/MESSAGE_FLOW.md notes /
    # the n8n-api-gotchas memory). This is the UUID currently live in production;
    # generate a fresh one only if re-creating the workflow from scratch.
    "webhookId": "d020c781-3098-4a23-af8d-f4d0d937fec2",
    "credentials": {"telegramApi": TELEGRAM_CRED},
    "id": "03d66a5a-62cb-40c3-a3f5-ab429b802ba2"
})
add_node(if_node("Is Authorized User", "={{$json.message.from.id}}", 5765059635, "number", "equals", [220, 0], "c7f2cd5a-096a-47f0-915d-ef47cc76bdea"))
add_node({"parameters": {}, "type": "n8n-nodes-base.noOp", "typeVersion": 1, "position": [440, 260], "name": "Ignore Unauthorized", "id": "9e00864e-19ff-4165-b87a-5c4576c55da9"})
add_node(code_node(
    "Detect AZ Tag",
    "const text = $json.message.text || '';\n"
    "const azMatch = /^\\/az\\s+/i.test(text);\n"
    "const cleanText = azMatch ? text.replace(/^\\/az\\s+/i, '').trim() : text;\n"
    "return [{ json: { ...$json, azMode: azMatch, cleanText, startTime: Date.now() } }];",
    [440, 0]
))

connect("Telegram Trigger", "Is Authorized User")
connect("Is Authorized User", "Detect AZ Tag", 0)
connect("Is Authorized User", "Ignore Unauthorized", 1)

# ---- Generic "submit + poll" pipeline builder ----
def build_poll_pipeline(prefix, submit_url, submit_body, status_url_expr, done_node, timeout_node, x0, y0):
    """
    prefix: e.g. 'Router' or 'Local'
    submit_url: RunPod /run URL
    submit_body: JSON body string for submit (references $json.cleanText)
    status_url_expr: python format string with {job_id_expr} placeholder for GET status URL
    done_node: name of node to connect to on success (already defined elsewhere)
    timeout_node: name of node to connect to on exhausted attempts
    Returns name of the "Submit" node (entry point) so caller can connect into it.
    """
    submit_name = f"Submit {prefix} Job"
    init_name = f"Init {prefix} State"
    wait_name = f"Wait {prefix}"
    check_name = f"Check {prefix} Job"
    merge_name = f"Merge {prefix} State"
    done_check = f"{prefix} Job Done?"
    attempts_check = f"{prefix} Attempts Exceeded?"

    add_node(http_node(submit_name, "POST", submit_url, [x0, y0], body=submit_body))
    add_node(code_node(
        init_name,
        f"return [{{ json: {{ ...$('Detect AZ Tag').item.json, {prefix.lower()}JobId: $json.id, {prefix.lower()}Attempts: 0 }} }}];",
        [x0 + 220, y0]
    ))
    add_node(wait_node(wait_name, WAIT_SECONDS, [x0 + 440, y0]))
    status_url = status_url_expr.format(job_id_expr=f"{{{{ $json.{prefix.lower()}JobId }}}}")
    add_node(http_node(check_name, "GET", status_url, [x0 + 660, y0], body=None))
    add_node(code_node(
        merge_name,
        f"const prior = $('{wait_name}').item.json;\n"
        f"return [{{ json: {{ ...prior, status: $json.status, output: $json.output, {prefix.lower()}Attempts: (prior.{prefix.lower()}Attempts || 0) + 1 }} }}];",
        [x0 + 880, y0]
    ))
    add_node(if_node(done_check, "={{$json.status}}", "COMPLETED", "string", "equals", [x0 + 1100, y0]))
    add_node(if_node(attempts_check, f"={{{{$json.{prefix.lower()}Attempts}}}}", MAX_ATTEMPTS, "number", "gte", [x0 + 1100, y0 + 220]))

    connect(submit_name, init_name)
    connect(init_name, wait_name)
    connect(wait_name, check_name)
    connect(check_name, merge_name)
    connect(merge_name, done_check)
    connect(done_check, done_node, 0)
    connect(done_check, attempts_check, 1)
    connect(attempts_check, timeout_node, 0)
    connect(attempts_check, wait_name, 1)   # loop back

    return submit_name

# ---- Short-term conversation history (fetched before classification) ----
add_node(postgres_node(
    "Get Recent History",
    "SELECT message, response FROM conversation_log ORDER BY created_at DESC LIMIT 6;",
    "={{ [] }}",
    [440, 220]
))
for n in nodes:
    if n["name"] == "Get Recent History":
        n["alwaysOutputData"] = True
connect("Detect AZ Tag", "Get Recent History")

add_node(code_node(
    "Build History Context",
    "const prior = $('Detect AZ Tag').item.json;\n"
    "const rows = $input.all().map(item => item.json).filter(r => r.message).reverse();\n"
    "let historyText = '';\n"
    "if (rows.length) {\n"
    "  historyText = 'Recent conversation (oldest to newest):\\n' + rows.map(r => 'User: ' + r.message + '\\nAssistant: ' + (r.response || '')).join('\\n') + '\\n\\n';\n"
    "}\n"
    "return [{ json: { ...prior, historyText } }];",
    [660, 220]
))
connect("Get Recent History", "Build History Context")

# ---- Router pipeline ----
add_node(code_node(
    "Extract Router Result",
    "const raw = $json.output[0].choices[0].message.content;\n"
    "let parsed;\n"
    "try { parsed = JSON.parse(raw); } catch (e) { parsed = { type: 'simple', confidence: 0, reasoning: 'router_parse_error', reply: null }; }\n"
    "return [{ json: { ...$json, ...parsed } }];",
    [2200, -120]
))
add_node(telegram_node(
    "Router Timeout Reply",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Sorry, the router model is still cold-starting (this can take a while after being idle). Please try again in a minute.",
    [2200, 120]
))

router_submit = build_poll_pipeline(
    "Router",
    f"https://api.runpod.ai/v2/{ROUTER_EP}/run",
    router_run_body(),
    "https://api.runpod.ai/v2/" + ROUTER_EP + "/status/{job_id_expr}",
    "Extract Router Result",
    "Router Timeout Reply",
    880, -120
)
# Router's Init step references $('Detect AZ Tag') by default (see build_poll_pipeline);
# override so it preserves historyText from Build History Context instead.
for n in nodes:
    if n["name"] == "Init Router State":
        n["parameters"]["jsCode"] = (
            "return [{ json: { ...$('Build History Context').item.json, routerJobId: $json.id, routerAttempts: 0 } }];"
        )
connect("Build History Context", router_submit)

# ---- Route by type (after router result) ----
add_node({
    "parameters": {
        "rules": {
            "values": [
                {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"}, "conditions": [{"leftValue": "={{$json.type}}", "rightValue": "simple", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "renameOutput": True, "outputKey": "simple"},
                {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"}, "conditions": [{"leftValue": "={{$json.type}}", "rightValue": "reminder", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "renameOutput": True, "outputKey": "reminder"},
                {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"}, "conditions": [{"leftValue": "={{$json.type}}", "rightValue": "project", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "renameOutput": True, "outputKey": "project"},
                {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"}, "conditions": [{"leftValue": "={{$json.type}}", "rightValue": "heavy", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "renameOutput": True, "outputKey": "heavy"},
                {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"}, "conditions": [{"leftValue": "={{$json.type}}", "rightValue": "presentation", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "renameOutput": True, "outputKey": "presentation"},
                {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"}, "conditions": [{"leftValue": "={{$json.type}}", "rightValue": "content", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "renameOutput": True, "outputKey": "content"},
                {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"}, "conditions": [{"leftValue": "={{$json.type}}", "rightValue": "status", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "renameOutput": True, "outputKey": "status"}
            ]
        },
        "options": {"fallbackOutput": "none"}
    },
    "type": "n8n-nodes-base.switch",
    "typeVersion": 3,
    "position": [2420, -120],
    "name": "Route By Type",
    "id": "route-by-type"
})
connect("Extract Router Result", "Route By Type")

add_node(if_node("Need 14B?", "={{ $json.azMode || !$json.reply }}", True, "boolean", "equals", [2640, -300]))
connect("Route By Type", "Need 14B?", 0)

add_node(telegram_node(
    "Send Reply (3B)",
    "={{$json.message.chat.id}}",
    "={{$json.reply}}\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $json.startTime) / 1000)).toFixed(1) }}s · no personal data used]_",
    [2860, -140]
))
connect("Need 14B?", "Send Reply (3B)", 1)

add_node(telegram_node(
    "Send Placeholder Reply",
    "={{$json.message.chat.id}}",
    "=Got it — classified as *{{$json.type}}* (confidence {{$json.confidence}}). Full handling for this type isn't built yet, coming in a later phase.\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $json.startTime) / 1000)).toFixed(1) }}s · classification only, no external model called]_",
    [2640, 120]
))
for output_idx in range(3, 6):
    connect("Route By Type", "Send Placeholder Reply", output_idx)

# ---- Local model pipeline (triggered from Need 14B? true branch) ----
add_node(code_node(
    "Extract Local Result",
    "return [{ json: { ...$json, localReply: $json.output[0].choices[0].message.content } }];",
    [3300, -420]
))
add_node(telegram_node(
    "Send Reply (14B)",
    "={{$json.message.chat.id}}",
    "={{$json.localReply}}\n\n_[Local · Qwen2.5-14B · {{ (((Date.now() - $json.startTime) / 1000)).toFixed(1) }}s · {{ $json.ragFactsUsed > 0 ? ($json.ragFactsUsed + ' fact' + ($json.ragFactsUsed === 1 ? '' : 's') + ' from your data used') : 'no personal data used' }}]_",
    [3520, -420]
))
add_node(telegram_node(
    "Local Timeout Reply",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Sorry, the local model is still cold-starting (this can take a while after being idle). Please try again in a couple minutes.",
    [3300, -180]
))

local_prompt_js = json.dumps(local_prompt)

add_node(http_node(
    "Query Qdrant",
    "POST",
    "http://qdrant:6333/collections/profile_facts/points/search",
    [3300, -620],
    body='={"vector": {{ JSON.stringify($json.output.data[0].embedding) }}, "limit": 3, "with_payload": true}'
))
add_node(http_node(
    "Query Qdrant Memory",
    "POST",
    "http://qdrant:6333/collections/conversation_memory/points/search",
    [3520, -700],
    body='={"vector": {{ JSON.stringify($(\'Embed Job Done?\').item.json.output.data[0].embedding) }}, "limit": 3, "with_payload": true}'
))
# Qdrant calls are internal network only, no RunPod auth needed
for n in nodes:
    if n["name"] in ("Query Qdrant", "Query Qdrant Memory"):
        n["parameters"].pop("authentication", None)
        n["parameters"].pop("nodeCredentialType", None)
        n.pop("credentials", None)

add_node(code_node(
    "Build Local Context",
    "const prior = $('Need 14B?').item.json;\n"
    f"const basePrompt = {local_prompt_js};\n"
    "const profileHits = ($('Query Qdrant').item.json.result || []).map(r => r.payload && r.payload.text).filter(Boolean);\n"
    "const memoryHits = ($json.result || []).map(r => r.payload && r.payload.text).filter(Boolean);\n"
    "const allFacts = [...profileHits, ...memoryHits];\n"
    "const factsBlock = allFacts.length ? ('\\n\\nRelevant facts about the user:\\n- ' + allFacts.join('\\n- ')) : '';\n"
    "return [{ json: { ...prior, localSystemPrompt: basePrompt + factsBlock, ragFactsUsed: allFacts.length } }];",
    [3740, -620]
))
add_node(code_node(
    "Embed Fallback Empty Context",
    "const prior = $('Need 14B?').item.json;\n"
    f"const basePrompt = {local_prompt_js};\n"
    "return [{ json: { ...prior, localSystemPrompt: basePrompt, ragFactsUsed: 0 } }];",
    [3300, -260]
))

embed_submit = build_poll_pipeline(
    "Embed",
    f"https://api.runpod.ai/v2/{EMBED_EP}/run",
    embed_run_body(),
    "https://api.runpod.ai/v2/" + EMBED_EP + "/status/{job_id_expr}",
    "Query Qdrant",
    "Embed Fallback Empty Context",
    2860, -620
)
connect("Need 14B?", embed_submit, 0)
connect("Query Qdrant", "Query Qdrant Memory")
connect("Query Qdrant Memory", "Build Local Context")

add_node(code_node(
    "Prep Local Submit Input",
    "return [{ json: $json }];",
    [3960, -420]
))
connect("Build Local Context", "Prep Local Submit Input")
connect("Embed Fallback Empty Context", "Prep Local Submit Input")

local_submit = build_poll_pipeline(
    "Local",
    f"https://api.runpod.ai/v2/{LOCAL_EP}/run",
    local_run_body(),
    "https://api.runpod.ai/v2/" + LOCAL_EP + "/status/{job_id_expr}",
    "Extract Local Result",
    "Local Timeout Reply",
    4160, -420
)
# Local's Init step references $('Detect AZ Tag') by default (see build_poll_pipeline);
# override so it preserves localSystemPrompt/ragFactsUsed from Prep Local Submit Input instead.
for n in nodes:
    if n["name"] == "Init Local State":
        n["parameters"]["jsCode"] = (
            "return [{ json: { ...$('Prep Local Submit Input').item.json, localJobId: $json.id, localAttempts: 0 } }];"
        )
connect("Prep Local Submit Input", local_submit)
connect("Extract Local Result", "Send Reply (14B)")

# ---- Memory extraction (fire-and-forget, runs alongside sending the reply) ----
add_node(code_node(
    "Normalize Reply (3B)",
    "const assistantReplyText = $json.reply;\n"
    "const memExtractInput = 'User said: \"' + $json.cleanText + '\"\\nAssistant replied: \"' + assistantReplyText + '\"';\n"
    "return [{ json: { ...$json, assistantReplyText, memExtractInput } }];",
    [2860, 20]
))
add_node(code_node(
    "Normalize Reply (14B)",
    "const assistantReplyText = $json.localReply;\n"
    "const memExtractInput = 'User said: \"' + $json.cleanText + '\"\\nAssistant replied: \"' + assistantReplyText + '\"';\n"
    "return [{ json: { ...$json, assistantReplyText, memExtractInput } }];",
    [3520, -40]
))
connect("Need 14B?", "Normalize Reply (3B)", 1)
connect("Extract Local Result", "Normalize Reply (14B)")

add_node(code_node(
    "Prep MemExtract Input",
    "return [{ json: $json }];",
    [4160, -140]
))
connect("Normalize Reply (3B)", "Prep MemExtract Input")
connect("Normalize Reply (14B)", "Prep MemExtract Input")

add_node(code_node(
    "Extract MemExtract Result",
    "const raw = ($json.output[0].choices[0].message.content || '').trim();\n"
    "return [{ json: { ...$json, extractedFact: raw } }];",
    [4600, 20]
))
add_node(if_node("Is Memorable?", "={{$json.extractedFact}}", "NONE", "string", "notEquals", [4820, 20]))
add_node({"parameters": {}, "type": "n8n-nodes-base.noOp", "typeVersion": 1, "position": [5040, 180], "name": "Nothing To Remember", "id": "nothing-to-remember"})
add_node({"parameters": {}, "type": "n8n-nodes-base.noOp", "typeVersion": 1, "position": [5480, 180], "name": "Memory Embed Failed", "id": "memory-embed-failed"})

memextract_submit = build_poll_pipeline(
    "MemExtract",
    f"https://api.runpod.ai/v2/{ROUTER_EP}/run",
    memextract_run_body(),
    "https://api.runpod.ai/v2/" + ROUTER_EP + "/status/{job_id_expr}",
    "Extract MemExtract Result",
    "Nothing To Remember",
    4160, 20
)
# MemExtract's Init step references $('Detect AZ Tag') by default (see build_poll_pipeline);
# override so it preserves memExtractInput/assistantReplyText from Prep MemExtract Input instead.
for n in nodes:
    if n["name"] == "Init MemExtract State":
        n["parameters"]["jsCode"] = (
            "return [{ json: { ...$('Prep MemExtract Input').item.json, memextractJobId: $json.id, memextractAttempts: 0 } }];"
        )
connect("Prep MemExtract Input", memextract_submit)

add_node(code_node(
    "Prepare Memory Upsert",
    "return [{ json: { ...$json, memPointId: Date.now() } }];",
    [5040, -140]
))
add_node(http_node(
    "Upsert Memory Fact",
    "PUT",
    "http://qdrant:6333/collections/conversation_memory/points?wait=true",
    [5480, -140],
    body='={"points": [{"id": {{ $json.memPointId }}, "vector": {{ JSON.stringify($json.output.data[0].embedding) }}, "payload": {"text": {{ JSON.stringify($json.extractedFact) }}, "source_message": {{ JSON.stringify($json.cleanText) }}, "created_at": {{ JSON.stringify(new Date().toISOString()) }}}}]}'
))
for n in nodes:
    if n["name"] == "Upsert Memory Fact":
        n["parameters"].pop("authentication", None)
        n["parameters"].pop("nodeCredentialType", None)
        n.pop("credentials", None)

memembed_submit = build_poll_pipeline(
    "MemEmbed",
    f"https://api.runpod.ai/v2/{EMBED_EP}/run",
    memembed_run_body(),
    "https://api.runpod.ai/v2/" + EMBED_EP + "/status/{job_id_expr}",
    "Prepare Memory Upsert",
    "Memory Embed Failed",
    5040, -60
)
for n in nodes:
    if n["name"] == "Init MemEmbed State":
        n["parameters"]["jsCode"] = (
            "return [{ json: { ...$('Is Memorable?').item.json, memembedJobId: $json.id, memembedAttempts: 0 } }];"
        )
connect("Extract MemExtract Result", "Is Memorable?")
connect("Is Memorable?", memembed_submit, 0)
connect("Is Memorable?", "Nothing To Remember", 1)
connect("Prepare Memory Upsert", "Upsert Memory Fact")

# ---- Reminder extraction + storage (triggered from Route By Type "reminder" output) ----
add_node(code_node(
    "Prep Reminder Extract Input",
    "const now = new Date();\n"
    "const bakuTime = new Date(now.getTime() + 4 * 60 * 60 * 1000);\n"
    "const weekday = bakuTime.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' });\n"
    "const dateStr = bakuTime.toISOString().slice(0, 10);\n"
    "const timeStr = bakuTime.toISOString().slice(11, 16);\n"
    "const nowStr = weekday + ', ' + dateStr + ' ' + timeStr + ' +04:00';\n"
    "const reminderExtractInput = ($json.historyText || '') + 'Current date/time: ' + nowStr + '\\nUser message: \"' + $json.cleanText + '\"';\n"
    "return [{ json: { ...$json, reminderExtractInput } }];",
    [2860, 320]
))
connect("Route By Type", "Prep Reminder Extract Input", 1)

add_node(code_node(
    "Extract Reminder Result",
    "const raw = $json.output[0].choices[0].message.content;\n"
    "let parsed;\n"
    "try { parsed = JSON.parse(raw); } catch (e) { parsed = { action: 'create', id: null, content: $json.cleanText, due_date: null }; }\n"
    "return [{ json: { ...$json, extractedAction: parsed.action || 'create', extractedId: parsed.id || null, extractedContent: parsed.content || null, extractedDueDate: parsed.due_date || null } }];",
    [3520, 320]
))
add_node(telegram_node(
    "Reminder Extract Timeout Reply",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Sorry, I couldn't process that reminder right now (model still cold-starting). Please try again in a minute.",
    [3520, 500]
))

reminder_extract_submit = build_poll_pipeline(
    "ReminderExtract",
    f"https://api.runpod.ai/v2/{ROUTER_EP}/run",
    reminder_extract_run_body(),
    "https://api.runpod.ai/v2/" + ROUTER_EP + "/status/{job_id_expr}",
    "Extract Reminder Result",
    "Reminder Extract Timeout Reply",
    3080, 320
)
for n in nodes:
    if n["name"] == "Init ReminderExtract State":
        n["parameters"]["jsCode"] = (
            "return [{ json: { ...$('Prep Reminder Extract Input').item.json, reminderextractJobId: $json.id, reminderextractAttempts: 0 } }];"
        )
connect("Prep Reminder Extract Input", reminder_extract_submit)

add_node(if_node("Is Reminder Create?", "={{$json.extractedAction}}", "create", "string", "equals", [3740, 320]))
connect("Extract Reminder Result", "Is Reminder Create?")

add_node(if_node("Has Due Date?", "={{ !!$json.extractedDueDate }}", True, "boolean", "equals", [3960, 220]))
connect("Is Reminder Create?", "Has Due Date?", 0)

add_node(postgres_node(
    "Insert Reminder",
    "INSERT INTO tasks (content, due_date) VALUES ($1, $2) RETURNING id, content, due_date;",
    "={{ [$json.extractedContent, $json.extractedDueDate] }}",
    [4180, 120]
))
connect("Has Due Date?", "Insert Reminder", 0)

add_node(telegram_node(
    "Reminder Confirmed",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Got it — I'll remind you: *{{$json.content}}* at {{ new Date(new Date($json.due_date).getTime() + 4*60*60*1000).toISOString().replace('T',' ').slice(0,16) }} (Baku time).\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $('Detect AZ Tag').item.json.startTime) / 1000)).toFixed(1) }}s · stored in Postgres]_",
    [4400, 120]
))
connect("Insert Reminder", "Reminder Confirmed")

add_node(telegram_node(
    "Reminder Needs Clarification",
    "={{$json.message.chat.id}}",
    "=I got that you want a reminder for \"{{$json.extractedContent}}\" but couldn't figure out when — could you give me a specific date/time?\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $json.startTime) / 1000)).toFixed(1) }}s]_",
    [4180, 320]
))
connect("Has Due Date?", "Reminder Needs Clarification", 1)

add_node(postgres_node(
    "Find Task (By Id or Content)",
    "SELECT id, content, due_date FROM tasks WHERE status != 'deleted' AND ( ($1::int IS NOT NULL AND id = $1::int) OR ($1::int IS NULL AND content ILIKE '%' || $2 || '%') ) ORDER BY id DESC LIMIT 1;",
    "={{ [$json.extractedId, $json.extractedContent] }}",
    [3960, 420]
))
for n in nodes:
    if n["name"] == "Find Task (By Id or Content)":
        n["alwaysOutputData"] = True
connect("Is Reminder Create?", "Find Task (By Id or Content)", 1)

add_node(if_node("Task Found?", "={{ $json.id !== undefined }}", True, "boolean", "equals", [4180, 420]))
connect("Find Task (By Id or Content)", "Task Found?")

add_node(if_node("Is Reminder Delete?", "={{ $('Extract Reminder Result').item.json.extractedAction }}", "delete", "string", "equals", [4400, 380]))
connect("Task Found?", "Is Reminder Delete?", 0)

add_node(postgres_node(
    "Soft Delete Task",
    "UPDATE tasks SET status = 'deleted' WHERE id = $1 RETURNING id, content;",
    "={{ [$json.id] }}",
    [4620, 300]
))
connect("Is Reminder Delete?", "Soft Delete Task", 0)

add_node(telegram_node(
    "Reminder Deleted Confirmed",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Deleted reminder: *{{$json.content}}* (id {{$json.id}}).\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $('Detect AZ Tag').item.json.startTime) / 1000)).toFixed(1) }}s · soft-deleted in Postgres]_",
    [4840, 300]
))
connect("Soft Delete Task", "Reminder Deleted Confirmed")

add_node(postgres_node(
    "Update Task",
    "UPDATE tasks SET content = COALESCE($2, content), due_date = COALESCE($3, due_date), remind_count = 0 WHERE id = $1 RETURNING id, content, due_date;",
    "={{ [$json.id, $('Extract Reminder Result').item.json.extractedContent, $('Extract Reminder Result').item.json.extractedDueDate] }}",
    [4620, 460]
))
connect("Is Reminder Delete?", "Update Task", 1)

add_node(telegram_node(
    "Reminder Updated Confirmed",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Updated reminder (id {{$json.id}}): *{{$json.content}}*{{ $json.due_date ? (' at ' + new Date(new Date($json.due_date).getTime() + 4*60*60*1000).toISOString().replace('T',' ').slice(0,16) + ' (Baku time)') : '' }}.\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $('Detect AZ Tag').item.json.startTime) / 1000)).toFixed(1) }}s · updated in Postgres]_",
    [4840, 460]
))
connect("Update Task", "Reminder Updated Confirmed")

add_node(telegram_node(
    "Reminder Not Found Reply",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=I couldn't find an existing reminder matching \"{{$('Extract Reminder Result').item.json.extractedContent || ('id ' + $('Extract Reminder Result').item.json.extractedId)}}\" to {{$('Extract Reminder Result').item.json.extractedAction}}.\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $('Detect AZ Tag').item.json.startTime) / 1000)).toFixed(1) }}s]_",
    [4400, 560]
))
connect("Task Found?", "Reminder Not Found Reply", 1)

# ---- Project extraction + storage (triggered from Route By Type "project" output) ----
add_node(code_node(
    "Prep Project Extract Input",
    "const now = new Date();\n"
    "const bakuTime = new Date(now.getTime() + 4 * 60 * 60 * 1000);\n"
    "const weekday = bakuTime.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' });\n"
    "const dateStr = bakuTime.toISOString().slice(0, 10);\n"
    "const timeStr = bakuTime.toISOString().slice(11, 16);\n"
    "const nowStr = weekday + ', ' + dateStr + ' ' + timeStr + ' +04:00';\n"
    "const projectExtractInput = ($json.historyText || '') + 'Current date/time: ' + nowStr + '\\nUser message: \"' + $json.cleanText + '\"';\n"
    "return [{ json: { ...$json, projectExtractInput } }];",
    [2860, 620]
))
connect("Route By Type", "Prep Project Extract Input", 2)

add_node(code_node(
    "Extract Project Result",
    "const raw = $json.output[0].choices[0].message.content;\n"
    "let parsed;\n"
    "try { parsed = JSON.parse(raw); } catch (e) { parsed = { action: 'create', id: null, name: $json.cleanText, type: 'personal', description: $json.cleanText, deadline: null, status: null }; }\n"
    "return [{ json: { ...$json, extractedAction: parsed.action, extractedId: parsed.id || null, extractedName: parsed.name || null, extractedType: parsed.type || null, extractedDescription: parsed.description || null, extractedDeadline: parsed.deadline || null, extractedStatus: parsed.status || null } }];",
    [3520, 620]
))
add_node(telegram_node(
    "Project Extract Timeout Reply",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Sorry, I couldn't process that project right now (model still cold-starting). Please try again in a minute.",
    [3520, 800]
))

project_extract_submit = build_poll_pipeline(
    "ProjectExtract",
    f"https://api.runpod.ai/v2/{ROUTER_EP}/run",
    project_extract_run_body(),
    "https://api.runpod.ai/v2/" + ROUTER_EP + "/status/{job_id_expr}",
    "Extract Project Result",
    "Project Extract Timeout Reply",
    3080, 620
)
for n in nodes:
    if n["name"] == "Init ProjectExtract State":
        n["parameters"]["jsCode"] = (
            "return [{ json: { ...$('Prep Project Extract Input').item.json, projectextractJobId: $json.id, projectextractAttempts: 0 } }];"
        )
connect("Prep Project Extract Input", project_extract_submit)

add_node(if_node("Is Create?", "={{$json.extractedAction}}", "create", "string", "equals", [3740, 620]))
connect("Extract Project Result", "Is Create?")

add_node(postgres_node(
    "Insert Project",
    "INSERT INTO projects (name, type, description, deadline) VALUES ($1, $2, $3, $4) RETURNING id, name, type, description, deadline;",
    "={{ [$json.extractedName, $json.extractedType, $json.extractedDescription, $json.extractedDeadline] }}",
    [3960, 500]
))
connect("Is Create?", "Insert Project", 0)

add_node(telegram_node(
    "Project Confirmed",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Got it — tracking new *{{$json.type}}* project: *{{$json.name}}*.{{ $json.deadline ? (' Deadline: ' + new Date(new Date($json.deadline).getTime() + 4*60*60*1000).toISOString().replace('T',' ').slice(0,16) + ' (Baku time).') : '' }}\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $('Detect AZ Tag').item.json.startTime) / 1000)).toFixed(1) }}s · stored in Postgres]_",
    [4180, 500]
))
connect("Insert Project", "Project Confirmed")

add_node(postgres_node(
    "Find Project (By Id or Name)",
    "SELECT id, name, type, status, deadline, description FROM projects WHERE status != 'deleted' AND ( ($1::int IS NOT NULL AND id = $1::int) OR ($1::int IS NULL AND name ILIKE '%' || $2 || '%') ) ORDER BY created_at DESC LIMIT 1;",
    "={{ [$json.extractedId, $json.extractedName] }}",
    [3960, 740]
))
for n in nodes:
    if n["name"] == "Find Project (By Id or Name)":
        n["alwaysOutputData"] = True
connect("Is Create?", "Find Project (By Id or Name)", 1)

add_node(if_node("Project Found?", "={{ $json.id !== undefined }}", True, "boolean", "equals", [4180, 740]))
connect("Find Project (By Id or Name)", "Project Found?")

add_node(if_node("Is Delete?", "={{ $('Extract Project Result').item.json.extractedAction }}", "delete", "string", "equals", [4400, 640]))
connect("Project Found?", "Is Delete?", 0)

add_node(postgres_node(
    "Soft Delete Project",
    "UPDATE projects SET status = 'deleted' WHERE id = $1 RETURNING id, name;",
    "={{ [$json.id] }}",
    [4620, 540]
))
connect("Is Delete?", "Soft Delete Project", 0)

add_node(telegram_node(
    "Project Deleted Confirmed",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Deleted project: *{{$json.name}}* (id {{$json.id}}).\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $('Detect AZ Tag').item.json.startTime) / 1000)).toFixed(1) }}s · soft-deleted in Postgres]_",
    [4840, 540]
))
connect("Soft Delete Project", "Project Deleted Confirmed")

add_node(postgres_node(
    "Update Project",
    "UPDATE projects SET name = COALESCE($2, name), description = COALESCE($3, description), status = COALESCE($4, status), deadline = COALESCE($5, deadline) WHERE id = $1 RETURNING id, name, type, status, deadline, description;",
    "={{ [$json.id, null, $('Extract Project Result').item.json.extractedDescription, $('Extract Project Result').item.json.extractedStatus, $('Extract Project Result').item.json.extractedDeadline] }}",
    [4620, 740]
))
connect("Is Delete?", "Update Project", 1)

add_node(telegram_node(
    "Project Updated Confirmed",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Updated *{{$json.name}}* (id {{$json.id}}) — status: *{{$json.status}}*{{ $json.deadline ? (', deadline: ' + new Date(new Date($json.deadline).getTime() + 4*60*60*1000).toISOString().replace('T',' ').slice(0,16) + ' (Baku time)') : '' }}{{ $json.description ? (', description: ' + $json.description) : '' }}.\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $('Detect AZ Tag').item.json.startTime) / 1000)).toFixed(1) }}s · updated in Postgres]_",
    [4840, 740]
))
connect("Update Project", "Project Updated Confirmed")

add_node(telegram_node(
    "Project Not Found Reply",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=I couldn't find an existing project matching \"{{$('Extract Project Result').item.json.extractedName || ('id ' + $('Extract Project Result').item.json.extractedId)}}\" to {{$('Extract Project Result').item.json.extractedAction}}.{{ $('Extract Project Result').item.json.extractedAction === 'update' ? ' Want to create it as a new project instead?' : '' }}\n\n_[Router · Qwen2.5-3B · {{ (((Date.now() - $('Detect AZ Tag').item.json.startTime) / 1000)).toFixed(1) }}s]_",
    [4400, 900]
))
connect("Project Found?", "Project Not Found Reply", 1)

# ---- Status query (triggered from Route By Type "status" output) ----
add_node(postgres_node(
    "Get Active Projects (Status)",
    "SELECT id, name, type, status, deadline FROM projects WHERE status NOT IN ('done', 'deleted') ORDER BY deadline NULLS LAST;",
    "={{ [] }}",
    [2860, 1040]
))
for n in nodes:
    if n["name"] == "Get Active Projects (Status)":
        n["alwaysOutputData"] = True
connect("Route By Type", "Get Active Projects (Status)", 6)

add_node(postgres_node(
    "Get Pending Tasks (Status)",
    "SELECT id, content, due_date, remind_count FROM tasks WHERE status = 'pending' ORDER BY due_date NULLS LAST;",
    "={{ [] }}",
    [3080, 1040]
))
for n in nodes:
    if n["name"] == "Get Pending Tasks (Status)":
        n["alwaysOutputData"] = True
connect("Get Active Projects (Status)", "Get Pending Tasks (Status)")

status_context_code = (
    "const projects = $('Get Active Projects (Status)').all().map(item => item.json).filter(p => p.name);\n"
    "const tasks = $input.all().map(item => item.json).filter(t => t.content);\n"
    "let data = '';\n"
    "if (projects.length) {\n"
    "  data += 'Projects:\\n';\n"
    "  for (const p of projects) {\n"
    "    const deadlineStr = p.deadline ? new Date(new Date(p.deadline).getTime() + 4*60*60*1000).toISOString().slice(0,10) : 'no deadline';\n"
    "    data += '- id ' + p.id + ': ' + p.name + ' | type: ' + p.type + ' | status: ' + p.status + ' | deadline: ' + deadlineStr + '\\n';\n"
    "  }\n"
    "} else {\n"
    "  data += 'Projects: none tracked.\\n';\n"
    "}\n"
    "if (tasks.length) {\n"
    "  data += '\\nReminders:\\n';\n"
    "  for (const t of tasks) {\n"
    "    const dueStr = t.due_date ? new Date(new Date(t.due_date).getTime() + 4*60*60*1000).toISOString().slice(0,16).replace('T',' ') + ' Baku time' : 'no due date';\n"
    "    const firedNote = t.remind_count > 0 ? ', already notified' : '';\n"
    "    data += '- id ' + t.id + ': ' + t.content + ' | due: ' + dueStr + firedNote + '\\n';\n"
    "  }\n"
    "} else {\n"
    "  data += '\\nReminders: none pending.\\n';\n"
    "}\n"
    f"const basePrompt = {local_prompt_js};\n"
    "const localSystemPrompt = basePrompt + '\\n\\nThe user is asking about their real tracked projects/reminders. Here is the actual current data from the database, including each item\\'s numeric id (the user may reference these ids later to update/delete a specific item, so ALWAYS include the id when listing more than one item) — answer their specific question using ONLY this data, tailored to what they asked (don\\'t just dump everything if they asked something narrower). If the data doesn\\'t cover what they asked, say so honestly instead of guessing:\\n\\n' + data;\n"
    "return [{ json: { ...$('Detect AZ Tag').item.json, localSystemPrompt } }];"
)
add_node(code_node("Build Status Context", status_context_code, [3300, 1040]))
connect("Get Pending Tasks (Status)", "Build Status Context")

add_node(code_node(
    "Extract Status Local Result",
    "return [{ json: { ...$json, statusReplyText: $json.output[0].choices[0].message.content } }];",
    [4160, 1040]
))
add_node(telegram_node(
    "Status Local Timeout Reply",
    "={{$('Detect AZ Tag').item.json.message.chat.id}}",
    "=Sorry, I fetched your data but the model that summarizes it is still cold-starting. Please try again in a couple minutes.",
    [4160, 1220]
))

status_local_submit = build_poll_pipeline(
    "StatusLocal",
    f"https://api.runpod.ai/v2/{LOCAL_EP}/run",
    local_run_body(),
    "https://api.runpod.ai/v2/" + LOCAL_EP + "/status/{job_id_expr}",
    "Extract Status Local Result",
    "Status Local Timeout Reply",
    3520, 1040
)
for n in nodes:
    if n["name"] == "Init StatusLocal State":
        n["parameters"]["jsCode"] = (
            "return [{ json: { ...$('Build Status Context').item.json, statuslocalJobId: $json.id, statuslocalAttempts: 0 } }];"
        )
connect("Build Status Context", status_local_submit)

add_node(telegram_node(
    "Send Status Reply",
    "={{$json.message.chat.id}}",
    "={{$json.statusReplyText}}\n\n_[Local · Qwen2.5-14B · {{ (((Date.now() - $json.startTime) / 1000)).toFixed(1) }}s · real Postgres data used]_",
    [4840, 1040]
))
connect("Extract Status Local Result", "Send Status Reply")

# ---- Conversation logging (fan-out from each terminal reply, feeds short-term history) ----
add_node(postgres_node(
    "Log Conversation",
    "INSERT INTO conversation_log (message, response, task_type) VALUES ($1, $2, $3);",
    "={{ [$json.logMessage, $json.logResponse, $json.logTaskType] }}",
    [5700, 0]
))

def add_log_prep(name, response_expr, task_type, position, source, source_out=0):
    add_node(code_node(
        name,
        "return [{ json: { logMessage: $('Detect AZ Tag').item.json.cleanText, "
        f"logResponse: {response_expr}, logTaskType: '{task_type}' }} }}];",
        position
    ))
    connect(source, name, source_out)
    connect(name, "Log Conversation")

add_log_prep(
    "Prep Log (3B)",
    "$json.reply",
    "simple",
    [3080, -140],
    "Need 14B?", 1
)
add_log_prep(
    "Prep Log (Placeholder)",
    "'Classified as ' + $json.type + ', not yet handled'",
    "unbuilt",
    [2860, 260],
    "Route By Type", 3
)
for extra_out in (4, 5):
    connect("Route By Type", "Prep Log (Placeholder)", extra_out)
add_log_prep(
    "Prep Log (14B)",
    "$json.localReply",
    "simple_14b",
    [3740, -420],
    "Extract Local Result"
)
add_log_prep(
    "Prep Log (Reminder Confirmed)",
    "'Reminder set: ' + $json.content + ' at ' + $json.due_date",
    "reminder",
    [4400, 180],
    "Insert Reminder"
)
add_log_prep(
    "Prep Log (Reminder Clarify)",
    "'Asked for date/time clarification for: ' + $json.extractedContent",
    "reminder_clarify",
    [4180, 480],
    "Has Due Date?", 1
)
add_log_prep(
    "Prep Log (Reminder Deleted)",
    "'Deleted reminder: ' + $json.content + ' (id ' + $json.id + ')'",
    "reminder_delete",
    [4840, 600],
    "Soft Delete Task"
)
add_log_prep(
    "Prep Log (Reminder Updated)",
    "'Updated reminder: ' + $json.content + ' (id ' + $json.id + ')'",
    "reminder_update",
    [4840, 700],
    "Update Task"
)
add_log_prep(
    "Prep Log (Reminder Not Found)",
    "'Could not find reminder matching: ' + ($('Extract Reminder Result').item.json.extractedContent || ('id ' + $('Extract Reminder Result').item.json.extractedId)) + ' for action: ' + $('Extract Reminder Result').item.json.extractedAction",
    "reminder_not_found",
    [4620, 800],
    "Task Found?", 1
)
add_log_prep(
    "Prep Log (Project Confirmed)",
    "'Created project: ' + $json.name + ' (' + $json.type + ')'",
    "project_create",
    [4400, 460],
    "Insert Project"
)
add_log_prep(
    "Prep Log (Project Updated)",
    "'Updated project: ' + $json.name + ' to status ' + $json.status",
    "project_update",
    [4840, 700],
    "Update Project"
)
add_log_prep(
    "Prep Log (Project Not Found)",
    "'Could not find project matching: ' + ($('Extract Project Result').item.json.extractedName || ('id ' + $('Extract Project Result').item.json.extractedId)) + ' for action: ' + $('Extract Project Result').item.json.extractedAction",
    "project_not_found",
    [4620, 970],
    "Project Found?", 1
)
add_log_prep(
    "Prep Log (Project Deleted)",
    "'Deleted project: ' + $json.name + ' (id ' + $json.id + ')'",
    "project_delete",
    [4840, 460],
    "Soft Delete Project"
)
add_log_prep(
    "Prep Log (Status)",
    "$json.statusReplyText",
    "status",
    [4840, 1220],
    "Extract Status Local Result"
)

workflow = {
    "name": "Telegram - Personal AI Agent (router + local model)",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1"}
}

out_path = os.path.join(os.path.dirname(__file__), '..', 'n8n', 'workflows', 'telegram-agent.json')
with open(out_path, 'w') as f:
    json.dump(workflow, f, indent=2)

print("written, node count:", len(nodes))
