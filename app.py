import os
import re
import warnings
import streamlit as st
import streamlit.components.v1 as components
from streamlit_mic_recorder import speech_to_text
from google import genai
from google.genai import types
from tavily import TavilyClient

warnings.filterwarnings("ignore")

# 1. Cấu hình giao diện Streamlit
st.set_page_config(page_title="AI Minh Assistant", page_icon="🤖", layout="centered")
st.title("🤖 Trợ Lý AI Minh")
st.caption("Người bạn thân thiết & Người thầy uyên bác (Tích hợp Tra cứu Web & Quản lý Chat)")

# 2. Khai báo API Key & Client (Lấy từ Environment / Streamlit Secrets)
GEMINI_KEY = os.getenv("GEMINI_KEY", "")
TAVILY_KEY = os.getenv("TAVILY_KEY", "")

@st.cache_resource
def init_clients():
    ai_client = genai.Client(api_key=GEMINI_KEY)
    tavily_client = TavilyClient(api_key=TAVILY_KEY)
    return ai_client, tavily_client

client, tavily = init_clients()

# Tự động quét TOÀN BỘ danh sách Model khả dụng từ Google API
@st.cache_data(ttl=3600)
def fetch_available_models():
    default_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    try:
        fetched_models = []
        for m in client.models.list():
            methods = getattr(m, 'supported_generation_methods', []) or getattr(m, 'supported_methods', []) or getattr(m, 'supported_actions', [])
            if "generateContent" in methods or "generate_content" in methods:
                name = m.name.replace("models/", "")
                fetched_models.append(name)
        return fetched_models if fetched_models else default_models
    except Exception:
        return default_models

AVAILABLE_MODELS = fetch_available_models()

# Hạn ngạch miễn phí ước tính hàng ngày
MAX_DAILY_FREE_QUOTA = 1500

if "used_quota" not in st.session_state:
    st.session_state.used_quota = 0

# 3. Tối ưu hóa câu hỏi người dùng
def optimize_prompt(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', text).strip()
    cleaned = re.sub(r'^(cho tôi hỏi|cho hỏi|mình muốn hỏi|bạn ơi|dạ|ạ)\s*', '', cleaned, flags=re.IGNORECASE)
    return cleaned

# 4. Tra cứu Web thông minh
def should_search_web(query: str) -> bool:
    keywords = [
        "hôm nay", "hôm qua", "ngày mai", "mới nhất", "hiện tại", "bây giờ",
        "giá vàng", "thời tiết", "tỷ số", "kết quả", "bóng đá", "tin tức",
        "thị trường", "chứng khoán", "lịch thi đấu", "ở đâu", "ai là"
    ]
    pattern = re.compile("|".join(keywords), re.IGNORECASE)
    return bool(pattern.search(query))

def search_web(query: str) -> str:
    try:
        results = tavily.search(query=query, max_results=3)
        context = "\n".join([f"- {r['title']}: {r['content']}" for r in results.get('results', [])])
        return context if context else "Không tìm thấy kết quả phù hợp."
    except Exception as e:
        return f"Lỗi tra cứu web: {e}"

# 5. Gắn icon lĩnh vực tự động
def detect_category_icon(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ["bóng đá", "tỷ số", "trận đấu", "thể thao", "sea games", "v-league"]):
        return "⚽ Thể thao"
    elif any(k in q for k in ["thời tiết", "mưa", "nắng", "nhiệt độ", "bão"]):
        return "🌤️ Thời tiết"
    elif any(k in q for k in ["giá vàng", "chứng khoán", "tiền", "tài chính", "ngân hàng"]):
        return "💰 Tài chính"
    elif any(k in q for k in ["tin tức", "hôm nay", "mới nhất", "thời sự"]):
        return "📰 Tin tức"
    elif any(k in q for k in ["code", "lập trình", "python", "ai", "máy tính", "công nghệ"]):
        return "💻 Công nghệ"
    elif any(k in q for k in ["học", "sách", "giáo dục", "dịch", "tiếng anh"]):
        return "📚 Giáo dục"
    else:
        return "💬 Trò chuyện"

# 6. Xử lý Giọng Nói
def speak_text(text, voice_option):
    clean_text = text.replace("*", "").replace("#", "").replace('"', '\\"').replace("\n", " ")
    pitch = 1.25 if "Nữ" in voice_option else 0.85
    rate = 0.95 if "chậm" in voice_option else 1.05

    js_code = f"""
        <script>
            window.speechSynthesis.cancel();
            var msg = new SpeechSynthesisUtterance("{clean_text}");
            msg.lang = 'vi-VN';
            msg.rate = {rate};
            msg.pitch = {pitch};

            function selectVoice() {{
                var voices = window.speechSynthesis.getVoices();
                var isFemale = "{'Nữ' in voice_option}";
                
                if (isFemale === "True") {{
                    var femaleVoice = voices.find(function(v) {{
                        var name = v.name.toLowerCase();
                        return (v.lang.includes('vi') || v.lang.includes('VN')) && 
                               (name.includes('hoaimy') || name.includes('thutrang') || name.includes('linh') || name.includes('female') || name.includes('google'));
                    }});
                    if (femaleVoice) msg.voice = femaleVoice;
                }} else {{
                    var maleVoice = voices.find(function(v) {{
                        var name = v.name.toLowerCase();
                        return (v.lang.includes('vi') || v.lang.includes('VN')) && (name.includes('nam') || name.includes('male') || name.includes('an'));
                    }});
                    if (maleVoice) msg.voice = maleVoice;
                }}
                window.speechSynthesis.speak(msg);
            }}

            if (window.speechSynthesis.getVoices().length !== 0) {{
                selectVoice();
            }} else {{
                window.speechSynthesis.onvoiceschanged = selectVoice;
            }}
        </script>
    """
    components.html(js_code, height=0)

def stop_speech_and_listen():
    js_code = """
        <script>
            if (window.speechSynthesis.speaking) {
                window.speechSynthesis.cancel();
                setTimeout(function() {
                    var buttons = window.parent.document.querySelectorAll('button');
                    for (var btn of buttons) {
                        if (btn.innerText.includes('Bắt đầu nói')) {
                            btn.click();
                            break;
                        }
                    }
                }, 200);
            }
        </script>
    """
    components.html(js_code, height=0)

# 7. Khởi tạo Quản lý Lịch sử Chat Session
if "chats" not in st.session_state:
    st.session_state.chats = {}

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = "default"
    st.session_state.chats["default"] = {
        "title": "Trò chuyện mới",
        "category": "💬 Chung",
        "messages": [{"role": "assistant", "content": "Chào bạn! Mình là AI Minh. Bạn có thể gõ hoặc bấm nút mic để nói chuyện nhé!"}]
    }

# 8. Thanh Cấu hình & Lịch sử Chat (Sidebar)
with st.sidebar:
    remaining_quota = max(0, MAX_DAILY_FREE_QUOTA - st.session_state.used_quota)
    st.metric(label="📊 Lượt Free còn lại hôm nay", value=f"{remaining_quota}/{MAX_DAILY_FREE_QUOTA}")
    st.progress(remaining_quota / MAX_DAILY_FREE_QUOTA)

    st.markdown("---")
    if st.button("➕ Đoạn chat mới", use_container_width=True, type="primary"):
        new_id = f"chat_{len(st.session_state.chats) + 1}"
        st.session_state.chats[new_id] = {
            "title": "Trò chuyện mới",
            "category": "💬 Chung",
            "messages": [{"role": "assistant", "content": "Chào bạn! Mình là AI Minh. Bạn cần hỗ trợ gì hôm nay?"}]
        }
        st.session_state.current_chat_id = new_id
        st.rerun()

    st.markdown("---")
    st.header("🗂️ Lịch sử theo Lĩnh vực")
    
    for c_id, c_data in list(st.session_state.chats.items()):
        btn_label = f"{c_data['category']} | {c_data['title'][:18]}"
        is_active = (c_id == st.session_state.current_chat_id)
        if st.button(btn_label, key=f"btn_{c_id}", use_container_width=True, disabled=is_active):
            st.session_state.current_chat_id = c_id
            st.rerun()

    st.markdown("---")
    st.header("🤖 Cấu hình Model & Giọng nói")
    
    model_choice = st.selectbox(
        "Mô hình AI ưu tiên:",
        ["🔄 Tự động chuyển đổi (Auto-fallback)"] + AVAILABLE_MODELS
    )

    mute_mode = st.checkbox("🔇 Tắt âm thanh từ đầu (Chỉ đọc chữ)", value=False)
    
    if not mute_mode:
        enable_tts = st.checkbox("🔊 Bật đọc giọng nói (TTS)", value=True)
        voice_option = st.selectbox(
            "🎭 Chọn phong cách giọng AI:",
            ["Nữ truyền cảm (Miền Bắc/Nam)", "Nữ nhẹ nhàng, chậm rãi", "Nam chuẩn, trầm ấm", "Nam nhanh, linh hoạt"]
        )
    else:
        enable_tts = False
        voice_option = "Nữ truyền cảm (Miền Bắc/Nam)"
    
    if st.button("⏹️ Dừng đọc & Hỏi câu mới", use_container_width=True):
        stop_speech_and_listen()

# 9. Lấy dữ liệu đoạn chat hiện tại
current_chat = st.session_state.chats[st.session_state.current_chat_id]

for msg in current_chat["messages"]:
    st.chat_message(msg["role"]).write(msg["content"])

# 10. Giao diện Thu âm & Nhập liệu
st.write("🎙️ **Nói chuyện với AI:**")
voice_text = speech_to_text(
    start_prompt="🔴 Bắt đầu nói",
    stop_prompt="⏹️ Dừng & Gửi",
    language="vi-VN",
    just_once=True,
    use_container_width=True,
    key=f"speech_{st.session_state.current_chat_id}"
)

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

if voice_text:
    st.session_state.pending_prompt = voice_text

user_input = st.chat_input("Nhập câu hỏi của bạn...")
if user_input:
    st.session_state.pending_prompt = user_input

# 11. Xử lý Trả lời
if st.session_state.pending_prompt:
    raw_prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    
    prompt = optimize_prompt(raw_prompt)

    if prompt:
        if len(current_chat["messages"]) <= 1:
            current_chat["category"] = detect_category_icon(prompt)
            current_chat["title"] = prompt[:25]

        current_chat["messages"].append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("AI Minh đang suy nghĩ..."):
                res_text = None
                last_error_msg = ""
                system_instruction = "Bạn là Minh - người bạn thân thiết và người thầy uyên bác. Trả lời súc tích, chính xác."

                if should_search_web(prompt):
                    web_info = search_web(prompt)
                    full_prompt = f"Thông tin từ Web:\n{web_info}\n\nCâu hỏi: {prompt}"
                else:
                    full_prompt = prompt

                if model_choice == "🔄 Tự động chuyển đổi (Auto-fallback)":
                    candidate_models = AVAILABLE_MODELS
                else:
                    candidate_models = [model_choice] + [m for m in AVAILABLE_MODELS if m != model_choice]

                for model_candidate in candidate_models:
                    try:
                        response = client.models.generate_content(
                            model=model_candidate,
                            contents=full_prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                temperature=0.7
                            )
                        )
                        res_text = response.text
                        st.session_state.used_quota += 1
                        break
                    except Exception as model_err:
                        last_error_msg = str(model_err)
                        continue

                if res_text:
                    st.write(res_text)
                    current_chat["messages"].append({"role": "assistant", "content": res_text})
                    
                    if enable_tts and not mute_mode:
                        speak_text(res_text, voice_option)
                else:
                    if "429" in last_error_msg or "RESOURCE_EXHAUSTED" in last_error_msg:
                        st.error("🚫 **Đã hết lượt dùng Free của ngày hôm nay!** Vui lòng quay lại sau.")
                    else:
                        st.error(f"❌ **Lỗi kết nối API:** {last_error_msg}")