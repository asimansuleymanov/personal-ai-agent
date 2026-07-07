# Şəxsi AI Agent — Layihə Planı

## 1. Yüksək Səviyyəli Arxitektura (High-Level)

```
                              ┌─────────────────────┐
                              │        SİZ          │
                              │  (Telegram: mobil/   │
                              │   laptop, fərq yox)  │
                              └──────────┬───────────┘
                                         │
                              ┌──────────▼───────────┐
                              │    Telegram Bot API   │
                              └──────────┬───────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │         n8n — ORKESTRATOR (VM 1)          │
                    │   24/7 işləyir, bütün qərarları verir     │
                    └───┬──────────┬──────────┬──────────┬─────┘
                        │          │          │          │
              ┌─────────▼──┐ ┌─────▼────┐ ┌───▼────┐ ┌───▼─────────┐
              │ Router LLM │ │ Memory/  │ │Layihə/ │ │  Xarici AI  │
              │ (VM 2,     │ │ RAG DB   │ │Task DB │ │  API-lar    │
              │ serverless)│ │ (Qdrant) │ │(Postgre│ │(Claude/GPT) │
              │            │ │          │ │s)      │ │             │
              └────────────┘ └──────────┘ └────────┘ └─────────────┘
```

**Məntiq:** Siz Telegram-a yazırsınız → n8n mesajı qəbul edir → Router qərar verir (sadədir/ağırdır) → sadə isə local model cavablandırır, ağırdırsa xarici AI-a göndərilir → nəticə Telegram-a geri qayıdır. Paralel olaraq layihələr/deadline-lar Postgres-də saxlanır, cron job-lar xatırlatma göndərir.

---

## 2. Aşağı Səviyyəli Arxitektura (Low-Level)

### 2.1 Komponentlər və data axını

1. **Telegram Trigger (n8n node)** — yeni mesajı qəbul edir (webhook)
2. **Preprocessing node** — mesajı təmizləyir, istifadəçi ID-sini yoxlayır (yalnız siz icazəlisiniz)
3. **Embedding node** — mesajı vektora çevirir (kiçik embedding model, məs. `bge-small` və ya `nomic-embed`)
4. **Qdrant Query** — bu vektorla oxşar keçmiş qeydləri/layihə məlumatlarını tapır (top-5 nəticə)
5. **Router LLM çağırışı** — prompt: `[Sistem: sən router-san] + [Retrieved context] + [İstifadəçi mesajı]` → cavab formatı: `{"type": "simple|reminder|project|heavy|presentation|content", "confidence": 0.9}`
6. **Şərti budaqlanma (n8n IF/Switch node):**
   - `simple` → Local LLM-ə göndər, cavabı birbaşa Telegram-a qaytar
   - `reminder` → Postgres-ə INSERT (tarix, mətn), təsdiq mesajı qaytar
   - `project` → Postgres-ə INSERT/UPDATE (layihə cədvəli), təsdiq
   - `heavy` → Xarici AI API-a (Claude Sonnet/Haiku) göndər, cavabı formatla, qaytar
   - `presentation` → Kontent local/xarici modeldən alınır → pptx generator script-ə ötürülür → fayl Telegram-a göndərilir
   - `content` (mail/mesaj mətni) → Model kontenti yazır → Telegram-da göstərilir, siz təsdiqləyirsiniz

### 2.2 Verilənlər bazası sxemi (Postgres)

```sql
-- Profil məlumatları (RAG-a əlavə olaraq strukturlu hissə)
profile (id, key, value, updated_at)

-- Layihələr (iş, şəxsi, səyahət — hamısı eyni cədvəldə, "type" ilə ayrılır)
projects (
  id, name, type,              -- 'work' | 'personal' | 'travel'
  description, deadline,
  status,                       -- 'active' | 'done' | 'paused'
  priority, created_at
)

-- Alt-tapşırıqlar / xatırlatmalar
tasks (
  id, project_id (nullable),
  content, due_date,
  status,                       -- 'pending' | 'done'
  remind_count, last_reminded_at
)

-- Söhbət tarixçəsi (RAG üçün mənbə, həm də audit)
conversation_log (
  id, message, response, task_type, tokens_used, created_at
)
```

### 2.3 Qdrant kolleksiyaları

- `profile_facts` — sizin haqqınızda uzunmüddətli faktlar (üslub, iş sahəsi, tərcihlər)
- `project_context` — hər layihənin təfərrüatı (avtomatik `projects` cədvəlindən sync olunur)
- `conversation_memory` — son N həftənin söhbət xülasələri (uzun-müddətli yaddaş üçün)

### 2.4 Router prompt nümunəsi (development vaxtı dəqiqləşdiriləcək)

```
Sən tapşırıq router-sansan. İstifadəçinin mesajını təhlil et və JSON qaytar:
{"type": "simple|reminder|project|heavy|presentation|content", "reasoning": "qısa səbəb"}

Qaydalar:
- Sadə sual/status yoxlama/kiçik söhbət → simple
- Tarix/vaxt qeydi, xatırlatma tələbi → reminder
- Yeni layihə, deadline yeniləmə → project
- Kod yazmaq, dərin analiz, mürəkkəb yaradıcı iş → heavy
- Slayd/prezentasiya tələbi → presentation
- Mail/mesaj mətni yazma → content
```

---

## 3. Deployment Arxitekturası

```
┌─────────────────────────────────────────────────────────────┐
│  VM 1 — Hetzner Cloud (CX23, 2 vCPU/4GB) — 24/7 işləyir       │
│  Docker Compose ilə:                                          │
│  ├─ n8n (port 5678, Caddy/Nginx arxasında, SSL)                │
│  ├─ Postgres (port 5432, yalnız daxili şəbəkə)                 │
│  ├─ Qdrant (port 6333, yalnız daxili şəbəkə)                   │
│  └─ Caddy (avtomatik Let's Encrypt SSL, domain lazımdır)       │
└─────────────────────────────────────────────────────────────┘
                          │  HTTPS sorğu
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  VM 2 — RunPod Serverless Endpoint (yalnız sorğu vaxtı işə    │
│  düşür, sonra söndürülür)                                     │
│  ├─ Ollama/vLLM + seçilmiş model (aşağıda)                     │
│  └─ HTTP API endpoint (n8n bura POST edir)                     │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼ (yalnız "heavy" tip üçün)
┌─────────────────────────────────────────────────────────────┐
│  Xarici API-lar: Claude API, (lazım olsa) GPT API              │
└─────────────────────────────────────────────────────────────┘
```

**Tələb olunanlar:**
- Domain adı (n8n webhook üçün HTTPS lazımdır — Telegram HTTP webhook qəbul etmir)
- Hetzner hesabı + SSH key
- RunPod hesabı + API key
- Claude API key (console.anthropic.com)
- Telegram Bot Token (BotFather)

---

## 4. Tapşırıq Siyahısı (Çətinlik dərəcəsi ilə)

### Faza 1 — İnfrastruktur (əsas)
| Tapşırıq | Çətinlik |
|---|---|
| Hetzner VM yaratmaq, SSH qurmaq | Asan |
| Docker + Docker Compose quraşdırmaq | Asan |
| Domain-i VM-ə bağlamaq (DNS A record) | Asan |
| Caddy ilə SSL avtomatlaşdırma | Orta |
| n8n-i Docker Compose ilə qaldırmaq | Asan |
| Postgres qaldırmaq + sxem yaratmaq | Asan |
| Qdrant qaldırmaq | Asan |
| Telegram bot yaratmaq (BotFather) | Asan |
| n8n ↔ Telegram webhook inteqrasiyası | Orta |

### Faza 2 — Router və Local LLM
| Tapşırıq | Çətinlik |
|---|---|
| RunPod serverless endpoint qurmaq (Ollama template) | Orta |
| Model yükləmə və test (latency, keyfiyyət) | Orta |
| Router prompt dizaynı və test | Orta-Çətin |
| n8n-də router logic (Switch node) | Orta |
| Embedding modeli inteqrasiyası | Orta |

### Faza 3 — Memory/RAG
| Tapşırıq | Çətinlik |
|---|---|
| Profil sənədini yazmaq (siz haqqınızda) | Asan |
| Profili embed edib Qdrant-a yükləmək | Orta |
| Retrieval-ı router axınına qoşmaq | Orta |
| Söhbət tarixçəsindən avtomatik yaddaş yeniləmə | Çətin |

### Faza 4 — Layihələr / Tapşırıqlar / Xatırlatmalar
| Tapşırıq | Çətinlik |
|---|---|
| `projects`/`tasks` cədvəllərini yaratmaq | Asan |
| Təbii dildən struktur data çıxarma ("Tbilisi bileti 20-də açılır, xəbərdar et") | Orta-Çətin |
| Cron-based xatırlatma yoxlayıcısı | Orta |
| Deadline yaxınlaşanda avtomatik bildiriş | Asan-Orta |

### Faza 5 — Ağır Tapşırıqlar / Kontent
| Tapşırıq | Çətinlik |
|---|---|
| Claude API inteqrasiyası (n8n HTTP node) | Asan |
| Sadə/ağır qərar məntiqinin dəqiqləşdirilməsi | Orta |
| Prezentasiya generasiyası (pptx pipeline) | Çətin |
| Mail/mesaj kontenti generasiyası + təsdiq axını | Orta |

### Faza 6 — Gmail/Calendar (2-ci versiya — sonra müzakirə)
| Tapşırıq | Çətinlik |
|---|---|
| Google OAuth qurulması | Orta |
| Gmail trigger + cavabsız mail izləmə | Orta-Çətin |
| Calendar oxu/yazma inteqrasiyası | Orta |

---

## 5. Token İstifadəsi Təxmini

Fərziyyə: gündə ~30-50 qarşılıqlı əlaqə (mesaj + cavab)

| Əməliyyat | Tezliyi | Token/sorğu | Günlük cəm |
|---|---|---|---|
| Router (sinifləndirmə) | 30-50/gün | ~150-300 | ~7,500-15,000 |
| Local model (sadə cavab, RAG kontekstli) | 15-25/gün | ~800-1,500 | ~15,000-35,000 |
| Xarici AI (ağır tapşırıq: kod, analiz) | 3-6/gün | ~2,000-4,000 | ~9,000-24,000 |
| Prezentasiya/uzun kontent | 1-2/gün | ~3,000-6,000 | ~3,000-12,000 |

**Aylıq təxmini:**
- Local model (RunPod-da, sizin GPU xərcinizə daxildir): ~700,000-1,500,000 token/ay
- Xarici API (ödənişli, ayrıca xərc): ~350,000-1,000,000 token/ay

Bu, Claude Haiku səviyyəsində aylıq təxminən 5-15$ əlavə API xərci deməkdir (əgər əsasən Haiku istifadə etsəniz); Sonnet-lə qarışıq istifadə etsəniz bir qədər yüksək ola bilər. Development mərhələsində real istifadəyə görə dəqiqləşdirəcəyik.

---

## 6. Model Tövsiyələri

| Rol | Tövsiyə edilən model | Səbəb |
|---|---|---|
| **Router (sinifləndirmə)** | Qwen2.5-3B-Instruct (local, RunPod) | Çox sürətli, ucuz, sadə JSON output üçün 3B kifayətdir |
| **Local "sizi tanıyan" model** | Qwen2.5-14B-Instruct (local, RunPod) | RTX 4090/L40-da rahat işləyir, yaxşı çoxdilli dəstək, sürətli cavab |
| **Embedding** | bge-small-en / multilingual-e5-small | Yüngül, Qdrant üçün kifayət qədər dəqiq |
| **Ağır tapşırıqlar (kod, dərin analiz)** | Claude Haiku 4.5 (API) | Ucuz, sürətli, kod/analiz keyfiyyəti yüksək |
| **Prezentasiya/yaradıcı kontent (mail, mətn)** | Claude Sonnet 5 (API) | Yazı keyfiyyəti daha yüksək, strukturlaşdırılmış kontent üçün uyğun |

**Qeyd:** Router qərar məntiqi işə düşəndə, sistem sadəcə "sadə/ağır" deyil, həm də **qiymət/keyfiyyət** balansına görə Haiku və Sonnet arasında seçim edə bilər (məs. qısa cavab üçün Haiku, uzun/mühüm sənəd üçün Sonnet).

---

## 7. Növbəti Addım

Development başlayanda ilk addım **Faza 1**-dir (infrastruktur). Hazır olduğunuzda başlaya bilərik — Hetzner VM yaratma və Docker Compose faylı ilə başlamağı təklif edirəm.
