import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
"""Bot-room relay: 3 Hermes personas talk round-robin, feed dialogue.json."""
import asyncio
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

try:
    import edge_tts
except ImportError:
    edge_tts = None

BASE = os.path.dirname(os.path.abspath(__file__))
FEED = os.path.join(BASE, "dialogue.json")

BOTS = [
    {
        "id": "MOM",
        "name": "อาม้า",
        "color": "#fb7185",
        "persona": "อาม้า คนแม่ผู้ให้กำเนิดและเป็นผู้ก่อตั้งร้าน Sujiraporn Cafe' เป็นหญิงสูงอายุมาก ใจดี อบอุ่น มีเมตตา ยืนชงกาแฟอยู่ที่เคาน์เตอร์คอยพูดแทรกย้ำเตือนสติลูกๆ อยู่เสมอเรื่องความเสี่ยงในการใช้ชีวิตและการเงิน อย่าหลงเชื่อข่าวง่ายๆ มีสติ ไม่ทะเลาะเรื่องเมือง",
    },
    {
        "id": "BOSS",
        "name": "ไถ่",
        "color": "#e2e8f0",
        "persona": "ไถ่ พี่ใหญ่คนโตที่สุดในร่าง Ultra Instinct (สัญชาตญาณขั้นสุดยอด ผมสีเงินประกายแพลทินัม) น่านับถือ สุขุม ลุ่มลึก มองภาพรวมและรอบรู้การเมืองไทย นโยบายรัฐบาล เศรษฐกิจมหภาค กฎหมาย และเหตุการณ์บ้านเมืองปัจจุบัน วิเคราะห์อย่างลึกซึ้งเป็นกลาง",
    },
    {
        "id": "JOY",
        "name": "ตู่",
        "color": "#ffaa23",
        "persona": "ตู่ พี่สาวคนรองในร่างซูเปอร์ไซย่าสาว นิสัยสายฮาพลังล้นเหลือ ชอบติดตามข่าวการเมือง พรรคการเมือง การเลือกตั้ง และกระแสสังคมมาเล่าให้พี่น้องฟังอย่างออกรสออกชาติ",
    },
    {
        "id": "SAGE",
        "name": "อั่งม้อ",
        "color": "#ffcd2d",
        "persona": "อั่งม้อ พี่ชายคนรองในร่างซูเปอร์ไซย่าผมทองสุขุม ชอบจับประเด็นนโยบายรัฐบาล งบประมาณ ตัวเลขเศรษฐกิจปากท้อง และผลกระทบต่อประชาชน",
    },
    {
        "id": "CHILL",
        "name": "หม่อตี๋",
        "color": "#64e1ff",
        "persona": "หม่อตี๋ น้องชายคนเล็กสุดในร่างซูเปอร์ไซย่าบลู สุภาพ ช่างสังเกต ชอบสะท้อนมุมมองของคนรุ่นใหม่ที่มีต่อสังคมและการพัฒนาประเทศ",
    },
]
import urllib.request
import xml.etree.ElementTree as ET
import random

TOPIC_BASE = "สถานการณ์การบ้านการเมืองไทย และข่าวที่เป็นกระแส Talk of The Town สดใหม่ที่สุดในสังคมไทยวันนี้"

_last_news_fetch = 0
_news_cache_pool = []
_current_headline_index = 0

def fetch_all_thai_news():
    global _last_news_fetch, _news_cache_pool
    now = time.time()
    # รีเฟรชข่าวสดใหม่ทุก 5 นาที เพื่อให้บทสนทนาทันกระแส Talk of The Town เสมอ
    if now - _last_news_fetch < 300 and _news_cache_pool:
        return _news_cache_pool

    feeds = [
        "https://news.thaipbs.or.th/rss/politic.xml",
        "https://news.thaipbs.or.th/rss/social.xml",
        "https://news.thaipbs.or.th/rss/economic.xml",
        "https://www.matichon.co.th/politics/feed",
        "https://www.matichon.co.th/economy/feed",
        "https://www.matichon.co.th/feed",
        "https://www.khaosod.co.th/politics/feed",
        "https://www.khaosod.co.th/breaking-news/feed",
        "https://www.thairath.co.th/rss/news",
    ]
    collected = []
    seen = set()
    for url in feeds:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                tree = ET.fromstring(resp.read())
                for it in tree.findall('.//item')[:5]:
                    t = it.find('title')
                    if t is not None and t.text:
                        clean_title = t.text.strip().replace('"', '').replace("'", "")
                        # Filter out very short or non-substantive titles
                        if len(clean_title) >= 12 and clean_title not in seen:
                            seen.add(clean_title)
                            collected.append(clean_title)
        except Exception:
            pass

    if collected:
        _news_cache_pool = collected
    else:
        _news_cache_pool = [
            "เปิดหีบเลือกตั้ง นายก อบจ.นนทบุรี คนทยอยใช้สิทธิคึกคัก",
            "ประเด็นตรวจสอบ สว. และข้อกังขาเรื่องเส้นเงิน",
            "มาตรการกระตุ้นเศรษฐกิจและการพยุงค่าครองชีพประชาชน",
            "สภาพอากาศเตือนฝนตกหนักน้ำท่วมฉับพลันทั่วไทย",
            "การเตรียมเลือกตั้งบอร์ดประกันสังคมรอบใหม่"
        ]
    _last_news_fetch = now
    return _news_cache_pool

def get_live_talk_of_the_town():
    global _current_headline_index
    pool = fetch_all_thai_news()
    if not pool:
        return "ประเด็นการเมืองและสถานการณ์สังคมไทยปัจจุบัน"
    
    # Pick 2-3 headlines and rotate so every round brings a completely fresh topic
    count = min(3, len(pool))
    idx = _current_headline_index % len(pool)
    selected = []
    for i in range(count):
        selected.append(pool[(idx + i) % len(pool)])
    _current_headline_index = (idx + 1) % len(pool)
    
    return " • ".join(selected)

SKIP_PREFIXES = (
    "⚠", "!!!", "This is Meta", "prompts and completions",
    "See current pricing", "It lowers the barrier", "scaling experiments",
    "for confidential", "same model", "Confirm only", "Proceeding in",
    "To acknowledge", "Use this model", "Model override", "session_id:",
    "Session:", "Title:", "Duration:", "Messages:", "Resume", "  hermes",
    "Query:", "Initializing", "──",
)

HEADER = (
    "คุณคือ {name} นั่งคุยกันในร้าน Sujiraporn Cafe’. "
    "บุคลิกของคุณ: {persona}. "
    "หัวข้อประเด็นข่าว Talk of The Town และกระแสบ้านเมืองสดใหม่ที่จะพูดคุยรอบนี้: {topic}. "
    "นี่คือบทสนทนาที่ผ่านมา (ภาษาไทย):\n{history}\n"
    "กฎสำคัญที่สุด: "
    "- หัวข้อและประเด็นสนทนา: ให้พูดคุยแลกเปลี่ยนความคิดเห็นเกี่ยวกับ 'ประเด็น Talk of The Town สดใหม่รอบนี้' อย่างมีชีวิตชีวา มีประเด็นใหม่ๆ ตลอดเวลา ไม่พูดวนเรื่องเดิมซ้ำๆ และต่อบทสนทนากันอย่างอบอุ่นในครอบครัว "
    "- เปลี่ยนเรื่องคุยตลอด: หากในบทสนทนาที่ผ่านมาเริ่มคุยเรื่องเดิมไป 1-2 รอบแล้ว ให้หยิบยกประเด็นข่าว Talk of The Town ใหม่ที่ระบุในหัวข้อขึ้นมาเปิดประเด็นหรือชวนพี่น้องคุยต่อทันที ห้ามพูดเรื่องเดิมซ้ำซาก! "
    "- การเขียนตัวเลข: ทุกครั้งที่มีการเอ่ยถึงตัวเลข (เช่น วันที่ เวลา สถิติ คะแนนเสียง มาตรากฎหมาย) ให้เขียนเป็นตัวเลขอารบิก 1, 2, 3... เสมอ ห้ามเขียนเป็นตัวหนังสือภาษาไทย เช่น มาตรา 157 หรือ วันที่ 20 "
    "- ภาษาที่ใช้ในบทสนทนา: ให้ใช้ภาษาไทยทั้งหมดเป็นหลัก ยกเว้นคำทับศัพท์ภาษาอังกฤษหรือชื่อเฉพาะที่นิยมใช้ทั่วไป (เช่น Talk of The Town, PR, AI, Live, App, Online, Social Media, Content, Trend, Soft Power, Check and Balance เป็นต้น) สามารถเขียนเป็นภาษาอังกฤษหรือทับศัพท์ได้ตามความเหมาะสม ให้บทสนทนาฟังดูเป็นธรรมชาติ "
    "- ทุกครั้งระบบจะอ่านออกเสียงเป็นภาษาไทยเท่านั้น ห้ามอ่านออกเสียงภาษาอังกฤษเด็ดขาด "
    "- ห้ามใส่ไอคอนอีโมจิ (เช่น ☕️, 😎, 😂, ⚡) ใดๆ ทั้งสิ้นในข้อความเด็ดขาด ให้เป็นข้อความตัวอักษรล้วนเท่านั้น! "
    "- ห้ามพูดข้อความซ้ำหรือก๊อปปี้ประโยคที่เคยพูดไปแล้วเด็ดขาด: ต้องมีมุมมองใหม่ ประเด็นใหม่ หรือตอบรับคำพูดล่าสุดของเพื่อนอย่างสร้างสรรค์เสมอ "
    "- เมนูกาแฟในร้าน: ถ้ามีการเอ่ยถึงกาแฟ ให้พูดถึงเฉพาะ 4 เมนูนี้เท่านั้น ได้แก่ 'เอสเพรสโซ่', 'ลาเต้', 'มอคค่า', หรือ 'อเมริกาโน่' (ห้ามเรียกว่าน้ำชาหรือกาแฟแปลกๆ) "
    "- ห้ามเอ่ยชื่อภาษาอังกฤษ Sage, Joy, Chill, เซจ, จอย, ชิล เด็ดขาด! "
    "- ห้ามใช้คำประหลาดหรือคำซ้ำเช่น uf uf หรือคำสั่งระบบ เช่น FINISH_THIS_TURN เด็ดขาด! "
    "- ห้ามใส่ชื่อตัวเองหรือคำเรียกคนอื่นขึ้นต้นข้อความ เช่น อย่าพิมพ์ 'ม้า', 'ไถ่', 'ตั่วเฮีย', 'ม้อ', 'เจ้า', 'อั่งม้อ', 'อั๊ว', 'พวกลื้อ' นำหน้าข้อความ ให้พูดได้เลยทันที "
    "ตอบเป็นภาษาไทยล้วน 1-2 ประโยคสั้นๆ สนทนาอบอุ่นและเป็นกันเองเหมือนครอบครัวนั่งคุยกันในร้านกาแฟ. "
    "ส่งเฉพาะคำตอบของคุณ ไม่มีเครื่องหมายคำพูด ไม่มีคำบรรยายฉาก ห้ามพิมพ์ภาษาอังกฤษเด็ดขาด.\n"
    "บทพูดภาษาไทยของ {name}:"
)

def load():
    try:
        with open(FEED, encoding="utf-8") as f:
            d = json.load(f)
            if isinstance(d, dict):
                return d.get("messages", [])
            elif isinstance(d, list):
                return d
            return []
    except Exception:
        return []


def save(msgs, topic=None):
    tmp = FEED + ".tmp"
    data = {
        "topic": topic or f"🔥 Talk of The Town สดใหม่วันนี้: {get_live_talk_of_the_town()}",
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "messages": msgs[-60:]
    }
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, FEED)


PROTECTED_WORDS = [
    "ความสัมพันธ์", "สัมพันธภาพ", "สัมพันธ์", "ผูกพัน", "พันธบัตร", "พันธมิตร", "พันธสัญญา",
    "พิพิธภัณฑ์", "พันตำรวจ", "ร้อยตำรวจ", "พันเอก", "ร้อยเอก", "พันโท", "ร้อยโท", "พันตรี", "ร้อยตรี",
    "สารพัน", "จัดสรร", "สังสรรค์", "รังสรรค์", "สวรรค์", "มหัศจรรย์", "รางวัล",
    "ความเสี่ยง", "เสี่ยง", "เรียบร้อย"
]

def convert_thai_numbers_to_arabic(text):
    if not text:
        return ""
    # 1. Thai digits ๐-๙ -> 0-9
    for td, ad in [('๐', '0'), ('๑', '1'), ('๒', '2'), ('๓', '3'), ('๔', '4'),
                   ('๕', '5'), ('๖', '6'), ('๗', '7'), ('๘', '8'), ('๙', '9')]:
        text = text.replace(td, ad)

    # 2. Protect vocabulary containing number syllables
    for i, w in enumerate(PROTECTED_WORDS):
        text = text.replace(w, f"__PROT_{i}__")

    # 3. Protect magnitudes following Arabic digits (e.g. 250 ล้าน, 1.4 หมื่นล้าน, 2 หมื่น, 5 แสน)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*(ล้าน|หมื่น|แสน|พัน|ร้อย)', r'\g<1> \g<2>', text)

    # Restore protected words
    for i, w in enumerate(PROTECTED_WORDS):
        text = text.replace(f"__PROT_{i}__", w)

    return re.sub(r'\s{2,}', ' ', text).strip()

ENGLISH_TO_THAI = [
    (r'(?i)\bbitcoin\b|\bbtc\b', 'บิตคอยน์'),
    (r'(?i)\bethereum\b|\beth\b', 'อีเธอเรียม'),
    (r'(?i)\bfunding\s*rate\b', 'ฟันดิงเรต'),
    (r'(?i)\bheatmap\b', 'ฮีตแมป'),
    (r'(?i)\bliquidation\b', 'การล้างพอร์ต'),
    (r'(?i)\bpre-?market\b', 'ช่วงก่อนตลาดเปิด'),
    (r'(?i)\bopening\s*bell\b', 'สัญญาณเปิดตลาด'),
    (r'(?i)\bcoinbase\b', 'คอยน์เบส'),
    (r'(?i)\bbinance\b', 'ไบแนนซ์'),
    (r'(?i)\bfed\b', 'เฟด'),
    (r'(?i)\bbond\s*yield\b', 'ผลตอบแทนพันธบัตร'),
    (r'(?i)\bfutures\b', 'ฟิวเจอร์ส'),
    (r'(?i)\bperpetual\b', 'เพอร์เพทชวล'),
    (r'(?i)\bsingle-?stock\b', 'หุ้นรายตัว'),
    (r'(?i)\bknight\s*capital\b', 'ไนท์แคปิตอล'),
    (r'(?i)\bcpi\b', 'ซีพีไอ'),
    (r'(?i)\bpce\b', 'พีซีอี'),
    (r'(?i)\baltcoins?\b', 'เหรียญทางเลือก'),
    (r'(?i)\bclarity\s*act\b', 'กฎหมายคลาวิตี้แอกต์'),
    (r'(?i)\bvolume\b', 'ปริมาณการซื้อขาย'),
    (r'(?i)\bpool\b', 'สภาพคล่อง'),
    (r'(?i)\bdemo\b', 'ทดลอง'),
    (r'(?i)\busd\b|\b\$\b', ' ดอลลาร์ '),
]


def clean(raw, bot_id=None):
    if not raw:
        return ""
    # กำจัดแท็กความคิด <think>...</think> ของโมเดลสาย Reasoning
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)
    # กำจัดบทบรรยายฉากหรือท่าทางในเครื่องหมายดอกจัน เช่น **อาม้ายิ้มกว้าง**
    raw = re.sub(r'\*\*.*?\*\*', '', raw)
    raw = re.sub(r'\(.*?\)', '', raw)
    
    ENGLISH_THOUGHT_PREFIXES = (
        "The user", "Here's", "Here is", "I need to", "Looking at", "In this",
        "I should", "Roleplay", "As an AI", "Let's think", "Step 1", "Analysis:",
        "Sure,", "Okay,", "Certainly"
    )
    
    lines = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith(SKIP_PREFIXES) or s.startswith(ENGLISH_THOUGHT_PREFIXES):
            continue
        # กำจัดขั้นตอนวิเคราะห์ภาษาอังกฤษ เช่น 1. **Analyze:**
        if re.match(r'^\d+\.\s+\*\*.*?\*\*', s):
            continue
        if re.match(r'^[a-zA-Z\s\*#\-:]{10,}$', s): # บรรทัดที่เป็นภาษาอังกฤษล้วน
            continue
        if s.startswith(('Output:', 'Output Generation:', 'Response:', 'บทพูด:', 'คำตอบ:')):
            s = re.sub(r'^(Output|Output Generation|Response|บทพูด|คำตอบ):\s*', '', s, flags=re.IGNORECASE)
        lines.append(s)
    
    text = " ".join(lines).strip()[:400]
    
    # Strip any URLs or Markdown link artifacts before stripping letters
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    
    # Strip any system leak / prompt artifact
    text = re.sub(r'(?i)Then FINISH_THIS_TURN.*', '', text)
    text = re.sub(r'(?i)FINISH_THIS_TURN.*', '', text)
    
    # Replace all old names to ensure 100% Thai names
    text = re.sub(r'(?i)sage', 'อั่งม้อ', text)
    text = re.sub(r'เซจ', 'อั่งม้อ', text)
    text = re.sub(r'(?i)joy', 'ตู่', text)
    text = re.sub(r'จอย', 'ตู่', text)
    text = re.sub(r'(?i)chill', 'หม่อตี๋', text)
    text = re.sub(r'หม่อตี๋|ม็อบตี๋|มอตี้|มือกตี๋|หม่อตี๋|หมอตี๋', 'หม่อตี๋', text)
    text = re.sub(r'^(อาม้า|ไถ่|พี่ไถ่|อาไถ่|ตั่วเฮีย|อาเจ้|พี่ตู่|ตุ๊ดตู่|ตู่|หยี่เฮีย|พี่อั่งม้อ|อั่งม้อ|หม่อตี๋|หม่อตี๋|หม่อตี๋):\s*', '', text)
    
    # Strip leading name/pronoun artifacts that model may prepend without colon
    LEADING_STRIP = r'^(คุณคือ|คุณตู่|อาม้า|ม้าลูก|ไถ่|พี่ไถ่|อาไถ่|ตั่วเฮีย|ตั่ว|อาเจ้|เจ้า|เจ้|พี่ตู่|ตุ๊ดตู่|ตู่|หยี่เฮีย|พี่อั่งม้อ|อั่งม้อ|หม่อตี๋|หม่อตี๋|หม่อตี๋|ม้า|ม้อ|เฮีย|เฮี๊ย|คุญ่า|อั๊ว|พวกลื้อ|อ้า๊ย|หลี่เฮีย|พี่ๆ)(\s*[:：]?\s*)'
    prev = None
    while prev != text:
        prev = text
        text = re.sub(LEADING_STRIP, '', text)
        text = re.sub(r'^[\d\s\.\,\-\—\:\;!\?\u0e50-\u0e59]+', '', text)
        text = re.sub(r'^[\u0e00-\u0e7f]\s*\d+(\s+|$)', '', text)
        text = re.sub(r'^\s+', '', text)
    
    # Strip garbage repetitive tokens or model hallucinations like 'uf uf'
    text = re.sub(r'\b[uU][fF]\b', '', text)
    text = re.sub(r'\s{2,}', ' ', text)

    # Convert all common English terms to pure Thai
    for eng_pattern, th_replacement in ENGLISH_TO_THAI:
        text = re.sub(eng_pattern, th_replacement, text)

    # Remove any leftover English words or letters completely so nothing is read in English
    
    # Strip broken markdown punctuation fragments (e.g. [ ](://..//-/-))
    text = re.sub(r'[\[\]\(\):/\\_~*`><]+', ' ', text)
    text = re.sub(r'^[.\s\'",\-]+', '', text)
    text = re.sub(r'["\'“”]', '', text)
    
    # Strip all emojis and special pictograms
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = re.sub(r'[\u2600-\u27bf\u2300-\u23ff\u2b50\ufe0f]', '', text)

    # Convert all Thai number words & Thai digits to Arabic numerals (1, 2, 3...)
    text = convert_thai_numbers_to_arabic(text)

    # Strip non-Thai, non-digit, non-basic punctuation characters to prevent TTS crashes
    text = re.sub(r'[^\u0e00-\u0e7fa-zA-Z0-9\s\.\,\-\:\;!\?\'\"]+', '', text)
    # Strip any trailing incomplete vowels or punctuation that choke TTS parsers
    # Strip dangling trailing prepositions/conjunctions
    text = re.sub(r'[\s,]+(และ|หรือ|กับ|ว่า|ที่|ได้|อย่า|เรื่อง|แต่|ของ|ใน|ถ้า|ก็|โดยเฉพาะ|เช่น|ครับเรื่อง|ค่ะเรื่อง|นะลูกเรื่อง)[\s\.\-]*$', '', text)
    text = re.sub(r'[\s\-เแโใไ]+$', '', text)

    text = re.sub(r'\s{2,}', ' ', text).strip()
    # ตรวจสอบความบริสุทธิ์ของภาษาไทย: สัดส่วนตัวอักษรไทยต้องไม่น้อยกว่า 70%
    thai_letters = len(re.findall(r'[\u0e00-\u0e7f]', text))
    eng_letters = len(re.findall(r'[a-zA-Z]', text))
    total_letters = thai_letters + eng_letters
    if thai_letters < 10 or total_letters == 0 or (thai_letters / total_letters) < 0.70:
        return None
    return text


OPENROUTER_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "poolside/laguna-s-2.1:free",
    "openrouter/free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
]

def get_api_key():
    k = os.environ.get("OPENROUTER_API_KEY")
    if k:
        return k
    candidate_paths = [
        os.path.join(BASE, "config.json"),
        os.path.join(os.path.dirname(BASE), "Antigravity", "Hermes_Gemini_Monitor", "config.json"),
        r"C:\Users\sager\Qsync\Antigravity\Hermes_Gemini_Monitor\config.json",
        r"C:\Users\PONG\Qsync\Antigravity\Hermes_Gemini_Monitor\config.json",
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    cfg = json.load(f)
                    if cfg.get("apiKey"):
                        return cfg["apiKey"]
            except Exception:
                pass
    return ""

def ask_openrouter(prompt):
    api_key = get_api_key()
    for model_name in OPENROUTER_MODELS:
        try:
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://botroom3d.sager.app",
                "X-Title": "BOT Room 3D"
            })
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": "คุณคือตัวละครสนทนาภาษาไทยในคาเฟ่ Sujiraporn Cafe' ตอบเฉพาะข้อความบทพูดภาษาไทยสั้นๆ 1-2 ประโยคเท่านั้น ห้ามแสดงความคิด ห้ามมีคำอธิบาย ห้ามมีภาษาอังกฤษ ไม่ใส่อีโมจิ"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 800,
                "temperature": 0.75
            }
            data = json.dumps(payload).encode("utf-8")
            with urllib.request.urlopen(req, data=data, timeout=25) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                choices = res.get("choices", [])
                if choices:
                    c = choices[0].get("message", {}).get("content")
                    if c and c.strip():
                        return c.strip()
        except urllib.error.HTTPError as he:
            print(f"OpenRouter ({model_name}) HTTP {he.code}: {he.reason}", file=sys.stderr)
            time.sleep(1)
        except Exception as ex:
            print(f"OpenRouter ({model_name}) error: {ex}", file=sys.stderr)
            time.sleep(1)
    return None

def ask(bot, history):
    raw_hist = "\n".join(f"{m.get('name', m['bot'])}: {m['text']}" for m in history[-10:] if m.get("bot") != "SYSTEM")
    lines = [ln for ln in raw_hist.split("\n") if "rate-limited" not in ln.lower() and "429" not in ln]
    hist = "\n".join(lines) if lines else ""
    talk_of_the_town = get_live_talk_of_the_town()
    topic = f"{TOPIC_BASE} -> ข่าว Talk of The Town สดๆ เวลานี้: [{talk_of_the_town}]"
    prompt = HEADER.format(
        name=bot["name"],
        persona=bot["persona"],
        topic=topic,
        history=hist or "(เพิ่งเริ่มบทสนทนารอบใหม่ ชวนพี่น้องในร้าน Sujiraporn Cafe’ คุยประเด็น Talk of The Town สดๆ วันนี้)"
    )

    # 1. Direct OpenRouter HTTP with automatic model failover
    text = ask_openrouter(prompt)
    if text:
        cleaned = clean(text, bot_id=bot["id"])
        if cleaned:
            return cleaned

    # 2. Secondary fallback: Hermes CLI if present on this machine
    hermes_candidates = [
        r"C:\Users\sager\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe",
        r"C:\Users\PONG\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe",
        "hermes.exe",
        "hermes"
    ]
    for hermes_bin in hermes_candidates:
        if os.path.exists(hermes_bin):
            try:
                proc = subprocess.run(
                    [hermes_bin, "chat", "-q", prompt, "-Q", "--provider", "openrouter", "--model", "openrouter/free"],
                    input=b"y\n",
                    capture_output=True,
                    timeout=60,
                )
                raw = proc.stdout or b""
                try:
                    out = raw.decode("utf-8")
                except UnicodeDecodeError:
                    out = raw.decode("utf-8", errors="replace")
                cleaned = clean(out, bot_id=bot["id"])
                if cleaned:
                    return cleaned
            except Exception as e:
                print(f"Hermes fallback error: {e}", file=sys.stderr)
    return None


AUDIO_DIR = os.path.join(BASE, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)
FFMPEG_EXE = None
for p in [
    r"C:\Users\sager\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.EXE",
    r"C:\Users\PONG\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.EXE",
    "ffmpeg.exe",
    "ffmpeg",
]:
    if os.path.exists(p):
        FFMPEG_EXE = p
        break

VOICE_CONFIG = {
    "MOM": {"voice": "th-TH-PremwadeeNeural", "rate": "-8%", "pitch_factor": 1.0},
    "BOSS": {"voice": "th-TH-NiwatNeural", "rate": "-4%", "pitch_factor": 0.95},
    "SAGE": {"voice": "th-TH-NiwatNeural", "rate": "+0%", "pitch_factor": 1.0},
    "JOY": {"voice": "th-TH-PremwadeeNeural", "rate": "-5%", "pitch_factor": 0.94},
    "CHILL": {"voice": "th-TH-NiwatNeural", "rate": "-8%", "pitch_factor": 1.05},
}

def make_audio(bot_id, text):
    if not edge_tts:
        return None
    try:
        cfg = VOICE_CONFIG.get(bot_id, {"voice": "th-TH-NiwatNeural", "rate": "+0%", "pitch_factor": 1.0})
        pf = cfg.get("pitch_factor", 1.0)
        # แปลงคำย่อและสัญลักษณ์ที่ทำให้ TTS สะดุด
        clean_tts = re.sub(r'ฉก\.', 'ฉก', text)
        clean_tts = re.sub(r'กมธ\.', 'กรรมาธิการ', clean_tts)
        clean_tts = re.sub(r'ผบ\.', 'ผู้บัญชาการ', clean_tts)
        clean_tts = re.sub(r'อบจ\.', 'อบจ', clean_tts)
        clean_tts = re.sub(r'สว\.', 'สว', clean_tts)
        clean_tts = re.sub(r'สส\.', 'สส', clean_tts)
        safe_text = re.sub(r'[\s\-เแโใไ]+$', '', clean_tts).strip()
        phonetic_text = safe_text.replace("หม่อตี๋", "ม่อตี๋") if bot_id in ["MOM", "JOY"] else safe_text
        if not safe_text:
            return None
        h = hashlib.md5((bot_id + safe_text + cfg["rate"] + str(pf)).encode("utf-8")).hexdigest()[:12]
        fname = f"msg_{bot_id.lower()}_{h}.mp3"
        fpath = os.path.join(AUDIO_DIR, fname)
        if not os.path.exists(fpath):
            tmp_path = os.path.join(AUDIO_DIR, f"tmp_{bot_id.lower()}_{h}.mp3")
            async def _gen():
                attempts = [
                    (cfg["voice"], cfg["rate"]),
                    (cfg["voice"], "+0%"),
                    ("th-TH-NiwatNeural", "-4%"),
                    ("th-TH-NiwatNeural", "+0%"),
                ]
                for v, r in attempts:
                    try:
                        if os.path.exists(tmp_path):
                            try: os.remove(tmp_path)
                            except Exception: pass
                        comm = edge_tts.Communicate(phonetic_text, v, rate=r)
                        await asyncio.wait_for(comm.save(tmp_path), timeout=8)
                        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1000:
                            return
                    except Exception:
                        pass
                print(f"All TTS attempts finished for {bot_id}", file=sys.stderr)
            asyncio.run(_gen())

            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1000:
                if pf != 1.0 and FFMPEG_EXE and os.path.exists(FFMPEG_EXE):
                    try:
                        filter_str = f"asetrate=24000*{pf:.3f},atempo={1.0/pf:.3f}"
                        res = subprocess.run([
                            FFMPEG_EXE, "-y", "-i", tmp_path,
                            "-af", filter_str,
                            fpath
                        ], capture_output=True, timeout=10)
                        if res.returncode == 0 and os.path.exists(fpath) and os.path.getsize(fpath) > 1000:
                            try: os.remove(tmp_path)
                            except Exception: pass
                            return f"audio/{fname}"
                    except Exception as fex:
                        print(f"ffmpeg pitch error for {bot_id}: {fex}", file=sys.stderr)
                try:
                    os.replace(tmp_path, fpath)
                except Exception:
                    pass

        if os.path.exists(fpath) and os.path.getsize(fpath) > 1000:
            return f"audio/{fname}"
        return None
    except Exception as ex:
        print(f"make_audio error for {bot_id}: {ex}", file=sys.stderr)
        return None


def is_too_similar(new_txt, past_msgs):
    if not new_txt:
        return True
    nt = new_txt.strip()
    # Check exact or near duplicate against last 12 messages
    for m in past_msgs[-12:]:
        pt = m.get("text", "").strip()
        if nt == pt:
            return True
        # Check high lexical overlap (e.g. repetition)
        if len(nt) > 10 and len(pt) > 10:
            common = set(nt).intersection(set(pt))
            overlap = len(common) / max(len(set(nt)), len(set(pt)))
            if overlap > 0.85 and (nt[:15] == pt[:15] or nt[-15:] == pt[-15:]):
                return True
    return False

_last_cloud_sync_time = 0
_cloud_sync_proc = None

def sync_to_cloud():
    global _last_cloud_sync_time, _cloud_sync_proc
    # 1. Mirror dialogue.json and audio to C:\Users\PONG\bot-room for local Tailscale/port 80
    alt_dir = r"C:\Users\PONG\bot-room"
    if os.path.exists(alt_dir) and os.path.abspath(alt_dir) != os.path.abspath(BASE):
        try:
            import shutil
            alt_dialogue = os.path.join(alt_dir, "dialogue.json")
            shutil.copyfile(FEED, alt_dialogue)
            alt_audio = os.path.join(alt_dir, "audio")
            os.makedirs(alt_audio, exist_ok=True)
            if os.path.exists(AUDIO_DIR):
                for f in os.listdir(AUDIO_DIR):
                    if f.endswith(".mp3"):
                        src = os.path.join(AUDIO_DIR, f)
                        dst = os.path.join(alt_audio, f)
                        if not os.path.exists(dst):
                            shutil.copyfile(src, dst)
        except Exception:
            pass

    # 2. Deploy to Cloudflare Workers custom domain botroom3d.sager.app (debounced every 60s)
    now = time.time()
    if _cloud_sync_proc is not None and _cloud_sync_proc.poll() is None:
        return # Still running previous deploy
    if now - _last_cloud_sync_time < 60:
        return # Debounce to avoid flooding

    try:
        _last_cloud_sync_time = now
        _cloud_sync_proc = subprocess.Popen(
            ["cmd", "/c", "npx", "wrangler", "deploy"],
            cwd=BASE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except Exception as e:
        print(f"sync_to_cloud error: {e}", file=sys.stderr)

def main():
    msgs = [m for m in load() if m.get("bot") != "SYSTEM"]
    current_topic = get_live_talk_of_the_town()
    save(msgs, topic=f"🔥 Talk of The Town สดใหม่วันนี้: {current_topic}")
    sync_to_cloud()
    loop_count = 0
    while True:
        loop_count += 1
        current_topic = get_live_talk_of_the_town()
        topic_header = f"🔥 Talk of The Town สดใหม่วันนี้: {current_topic}"
        for bot in BOTS:
            text = ask(bot, msgs)
            if text and not is_too_similar(text, msgs):
                audio_url = make_audio(bot["id"], text)
                entry = {
                    "bot": bot["id"],
                    "name": bot["name"],
                    "text": text,
                    "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                }
                if audio_url:
                    entry["audio"] = audio_url
                msgs.append(entry)
                save(msgs, topic=topic_header)
                sync_to_cloud()
                print(f"[{entry['ts']}] {bot['name']}: {text} (Audio: {audio_url})", flush=True)
            # จังหวะตอบโต้ธรรมชาติในร้านกาแฟ 15 วินาทีต่อคน
            time.sleep(15)

        # จังหวะพักผ่อนระหว่างรอบ 45 วินาที และดึงข่าว Talk of the Town สดใหม่รอบต่อไป
        time.sleep(45)


if __name__ == "__main__":
    main()