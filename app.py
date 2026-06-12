import os
import requests
from datetime import datetime, timedelta
import streamlit as st
from google import genai
from google.genai import types
from pricing_engine import calculate_packaging_cost, PACKAGING_MASTER
from fob_engine import calculate_fob_price, COMMODITY_FOB_MASTER, DOMESTIC_FREIGHT_COST_IDR
from pi_generator import generate_pi_pdf, CONFIRM_MESSAGES

# ── 1. CONFIGURATION & INITIALIZATION ────────────────────────────────────────
st.set_page_config(
    page_title="InTradeX-Mate - AI-Powered Trade Consultant",
    page_icon="assets/favicon.png",
    layout="wide"
)

# ── CSS: LOCK SIDEBAR WIDTH ───────────────────────────────────────────────────
st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            min-width: 270px !important;
            max-width: 270px !important;
        }
        [data-testid="stSidebarResizeHandle"] {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("API Key tidak ditemukan. Pastikan GEMINI_API_KEY sudah dikonfigurasi.")
    st.stop()

client = genai.Client(api_key=api_key)

# ── HELPER FUNCTION: LOAD KNOWLEDGE BASE (RAG) ───────────────────────────────
def load_knowledge_base():
    context = ""
    base_dir = "knowledge_base"
    folders = ["spices", "countries", "documents", "compliance", "incoterms"]
    if os.path.exists(base_dir):
        for subfolder in folders:
            folder_path = os.path.join(base_dir, subfolder)
            if os.path.exists(folder_path):
                for file in sorted(os.listdir(folder_path)):
                    if file.endswith(".md"):
                        try:
                            with open(os.path.join(folder_path, file), "r", encoding="utf-8") as f:
                                context += (
                                    f"\n\n===== {subfolder.upper()} | {file.upper()} =====\n"
                                    f"{f.read()}"
                                )
                        except Exception as e:
                            context += f"\n\nERROR LOADING {file}: {str(e)}"
    return context

knowledge_context = load_knowledge_base()

# ── 2. SIDEBAR UI & MULTILANGUAGE SELECTOR ───────────────────────────────────
st.sidebar.image("assets/favicon.png", width=150)

st.sidebar.markdown(
    """
    <div style='padding: 2px 0 0 0;'>
        <p style='font-size: 20px; font-weight: 700; margin: 0 0 2px 0; line-height: 1.2;'>InTradeX-Mate</p>
        <p style='font-size: 13px; color: gray; margin: 0 0 1px 0; line-height: 1.4;'>
            Your Trade Intelligence Partner<br>for Indonesian Spice Sourcing
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown(" ")

st.sidebar.caption("A strategic initiative from **MAGASTU** for Indonesian spice sourcing solutions.")

st.sidebar.markdown("---")

lang_option = st.sidebar.selectbox(
    "🌐 Select Language",
    ["English", "Deutsch", "Nederlands", "日本語", "한국어", "العربية", "Bahasa Indonesia"]
)

st.sidebar.markdown("---")

st.sidebar.markdown("**🤝 How InTradeX-Mate Supports You**")
st.sidebar.markdown(
    """
    🔍 Trade Intelligence & Market Insights  
    🌍 Export Market Exploration  
    🤝 Supplier Discovery & Evaluation  
    📦 Indonesian Spice Sourcing Support  
    💰 Live Quotation Estimation  
    🚢 FOB Pricing & Cost Analysis  
    📄 Export Documentation Guidance  
    🧠 AI-Assisted Decision Support  
    """
)

st.sidebar.markdown("---")

if st.sidebar.button("🗑️ Clear Chat History", use_container_width=True):
    st.session_state.messages = []
    st.session_state.current_calc_context = "No active calculation on screen."
    st.rerun()

st.sidebar.markdown("---")

st.sidebar.markdown(
    """
    <div style='text-align: center; padding: 6px 0 2px 0; opacity: 0.75;'>
        <span style='font-size: 11px; color: gray;'>InTradeX-Mate v1.0 &nbsp;|&nbsp; Powered by &nbsp;</span>
        <span style='font-size: 13px;'>✦</span>
        <span style='font-size: 12px; font-weight: 700;
                     background: linear-gradient(90deg, #4285F4, #EA4335, #FBBC05, #34A853);
                     -webkit-background-clip: text;
                     -webkit-text-fill-color: transparent;'>&nbsp;Gemini AI</span>
    </div>
    """,
    unsafe_allow_html=True
)

# ── 3. LIVE USD/IDR EXCHANGE RATE ────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_live_usd_idr():
    """Fetch live USD/IDR rate from open.er-api.com. Refreshes every hour."""
    try:
        resp = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=5
        )
        data = resp.json()
        if data.get("result") == "success" and "IDR" in data.get("rates", {}):
            rate = int(round(data["rates"]["IDR"]))
            updated_utc = data.get("time_last_update_utc", "")
            updated_short = updated_utc[:16] if updated_utc else "—"
            return rate, updated_short, True
    except Exception:
        pass
    return 17500, "—", False


# ── 4. DYNAMIC GREETING FUNCTION (WIB Timezone UTC+7) ───────────────────────
def get_greeting(lang):
    from datetime import timezone, timedelta
    wib = timezone(timedelta(hours=7))
    current_hour = datetime.now(wib).hour

    if 5 <= current_hour < 12:
        period = "morning"
    elif 12 <= current_hour < 18:
        period = "afternoon"
    else:
        period = "evening"          # 18:00–04:59 → evening (good night dihapus)

    greetings = {
        "English": {
            "morning":   "👋 Hi, good morning! Welcome to",
            "afternoon": "👋 Hi, good afternoon! Welcome to",
            "evening":   "👋 Hi, good evening! Welcome to",
        },
        "Deutsch": {
            "morning":   "👋 Guten Morgen! Willkommen bei",
            "afternoon": "👋 Guten Tag! Willkommen bei",
            "evening":   "👋 Guten Abend! Willkommen bei",
        },
        "Nederlands": {
            "morning":   "👋 Goedemorgen! Welkom bij",
            "afternoon": "👋 Goedemiddag! Welkom bij",
            "evening":   "👋 Goedenavond! Welkom bij",
        },
        "日本語": {
            "morning":   "👋 おはようございます。ようこそ",
            "afternoon": "👋 こんにちは。ようこそ",
            "evening":   "👋 こんばんは。ようこそ",
        },
        "한국어": {
            "morning":   "👋 좋은 아침입니다. 방문을 환영합니다",
            "afternoon": "👋 안녕하세요. 방문을 환영합니다",
            "evening":   "👋 좋은 저녁입니다. 방문을 환영합니다",
        },
        "العربية": {
            "morning":   "👋 صباح الخير، أهلاً بك في",
            "afternoon": "👋 مساء الخير، أهلاً بك في",
            "evening":   "👋 مساء الخير، أهلاً بك في",
        },
        "Bahasa Indonesia": {
            "morning":   "👋 Halo, selamat pagi. Selamat datang di",
            "afternoon": "👋 Halo, selamat siang. Selamat datang di",
            "evening":   "👋 Halo, selamat sore. Selamat datang di",
        }
    }

    return greetings[lang][period]

# ── 4. DYNAMIC WELCOME TEXTS ─────────────────────────────────────────────────
welcome_texts = {
    "English": {
        "title": "👋 Hi, how are you? Welcome to",
        "subtitle": "I'm your Trade Intelligence Consultant for Indonesian spices. I can help you with:",
        "bullets": [
            "**Spice sourcing** — Product specs, grades, origins",
            "**Export documents** — Invoice, COA, phytosanitary, B/L",
            "**Incoterms & pricing** — FOB, CIF, DDP calculations",
            "**Import regulations** — Regional compliance (EU, GCC, FDA)"
        ],
        "placeholder": "Ask me anything about Indonesian spices..."
    },
    "Deutsch": {
        "title": "👋 Hallo, wie geht es Ihnen? Willkommen bei",
        "subtitle": "Ich bin Ihr KI-Handelsberater für indonesische Gewürze. Ich kann Ihnen helfen bei:",
        "bullets": [
            "**Gewürzbeschaffung** — Produktspezifikationen, -qualitäten, -herkunft",
            "**Exportdokumente** — Rechnung, COA, Pflanzengesundheitszeugnis, B/L",
            "**Incoterms & Preise** — FOB-, CIF-, DDP-Berechnungen",
            "**Importbestimmungen** — Regionale Compliance (EU, GCC, FDA)"
        ],
        "placeholder": "Fragen Sie nach indonesischen Gewürzen, Bestimmungen, Preisen..."
    },
    "Nederlands": {
        "title": "👋 Hallo, hoe gaat het met u? Welkom bij",
        "subtitle": "Ik ben uw Trade Intelligence Consultant voor Indonesische specerijen. Ik kan u helpen met:",
        "bullets": [
            "**Inkoop van specerijen** — Productspecificaties, kwaliteiten, oorsprong",
            "**Exportdocumenten** — Factuur, COA, fytosanitair certificaat, B/L",
            "**Incoterms & prijsstelling** — FOB-, CIF-, DDP-berekeningen",
            "**Importregels** — Regionale naleving dan compliance (EU, GCC, FDA)"
        ],
        "placeholder": "Vraag naar de inkoop van Indonesische specerijen, regelgeving, prijzen..."
    },
    "日本語": {
        "title": "👋 こんにちは、お元気ですか？ ようこそ",
        "subtitle": "私はインドネシア産香辛料の貿易インテリジェンス・コンサルタントです。以下のような業務をサポートいたします：",
        "bullets": [
            "**スパイス調達** — 製品仕様、グレード、原産地情報",
            "**輸出関連書類** — インボイス、COA（分析証明書）、植物検疫証明書、B/L",
            "**インコタームズと価格計算** — FOB、CIF、DDPのシミュレーション",
            "**輸入規制** — 地域ごとのコンプライアンス（欧州連合、GCC、米FDAなど）"
        ],
        "placeholder": "インドネシア産スパイスの調達、規制、価格について質問する..."
    },
    "한국어": {
        "title": "👋 안녕하세요, 잘 지내셨나요? 방문을 환영합니다",
        "subtitle": "저는 인도네시아산 향신료 전문 무역 인테리전스 컨설턴트입니다. 다음과 같은 업무를 도와드릴 수 있습니다:",
        "bullets": [
            "**향신료 소싱** — 제품 규격, 등급, 원산지 정보",
            "**수출 서류** — 상업송장, COA(성분분석표), 식물검역증, 선하증권(B/L)",
            "**인코터즈 및 가격 책정** — FOB, CIF, DDP 산정 및 계산",
            "**수입 규제** — 지역별 통관 규정 준수 (EU, GCC, 미 FDA)"
        ],
        "placeholder": "인도네시아 향신료 소싱, 규제, 가격에 대해 문의하세요..."
    },
    "العربية": {
        "title": "مرحباً، كيف حالك؟ مرحباً بك في 🙏",
        "subtitle": "أنا مستشارك لتجارة التوابل الإندونيسية. يمكنني مساعدتك في:",
        "bullets": [
            "**مصادر التوابل** — مواصفات المنتج، الدرجات، والمنشأ",
            "**وثائق التصدير** — الفاتورة، شهادة التحليل، الشهادة الصحية، بوليصة الشحن",
            "**الشحن والتسعير** — حسابات FOB, CIF, DDP",
            "**لوائح الاستيراد** — الامتثال الإقليمي"
        ],
        "placeholder": "اسأل عن مصادر التوابل الإندونيسية، اللوائح, الأسعار..."
    },
    "Bahasa Indonesia": {
        "title": "👋 Halo, apa kabar? Selamat datang di",
        "subtitle": "Saya adalah Konsultan Perdagangan Internasional untuk rempah-rempah Indonesia. Saya dapat membantu Anda terkait dengan:",
        "bullets": [
            "**Sumber rempah** — Spesifikasi produk, grade, asal usul",
            "**Dokumen ekspor** — Invoice, COA, Karantina/Fitosanitari, B/L",
            "**Incoterms & harga** — Kalkulasi FOB, CIF, DDP",
            "**Regulasi impor** — Kepatuhan regional (EU, GCC, FDA)"
        ],
        "placeholder": "Tanyakan tentang sumber rempah Indonesia, regulasi, harga..."
    }
}

selected_lang = welcome_texts[lang_option]

LANGUAGE_MAP = {
    "English": "English",
    "Deutsch": "German",
    "Nederlands": "Dutch",
    "日本語": "Japanese",
    "한국어": "Korean",
    "العربية": "Arabic",
    "Bahasa Indonesia": "Indonesian"
}

# ── 5. DYNAMIC SYSTEM PROMPT ─────────────────────────────────────────────────
if "current_calc_context" not in st.session_state:
    st.session_state.current_calc_context = "No active calculation on screen."

live_calc_data = st.session_state.current_calc_context

SYSTEM_PROMPT = f"""
You are InTradeX-Mate, an advanced AI-powered Trade Intelligence Consultant representing Magastu Indoprime Group (MIG).

CURRENT LIVE CALCULATION DATA:
{live_calc_data}

IMPORTANT LANGUAGE RULE:
Always respond ONLY in {LANGUAGE_MAP[lang_option]}.
Never switch language unless explicitly requested by the user.

BUSINESS RULES:
- Use professional international trade terminology.
- Use information from the Knowledge Base whenever relevant.
- Refer to the live calculation data when the user asks about current pricing, packaging, logistics, sourcing, freight, or specifications shown on screen.
- Provide structured and commercially useful answers.

KNOWLEDGE BASE:
{knowledge_context}
"""

# ── 6. CHAT INTERACTIVE LOGIC & WELCOME SCREEN ───────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "fob_result" not in st.session_state:
    st.session_state.fob_result = None
if "fob_error" not in st.session_state:
    st.session_state.fob_error = None
# ── Keys untuk auto-sync Tab Sourcing → Tab FOB ───────────────────────────────
if "sync_commodity" not in st.session_state:
    st.session_state.sync_commodity = None
if "sync_volume" not in st.session_state:
    st.session_state.sync_volume = None
if "sync_packaging" not in st.session_state:
    st.session_state.sync_packaging = None
# ── Key reset counter untuk force-clear widget ────────────────────────────────
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0
if "sync_applied" not in st.session_state:
    st.session_state.sync_applied = True

live_rate, live_rate_updated, live_rate_ok = fetch_live_usd_idr()

# ── TRADE TOOLS: always rendered regardless of chat history ──────────────────
st.subheader(get_greeting(lang_option))
if len(st.session_state.messages) == 0:
    st.image("assets/intradex_logo.png", width="stretch")

tab_pack, tab_fob, tab_pi, tab_qt = st.tabs([
    "📦 Sourcing & Packaging Calculator",
    "🚢 FOB Commercial Calculator",
    "📄 Proforma Invoice Generator",
    "📋 Quotation Generator"
])

# ── TAB 1: PACKAGING CALCULATOR ──────────────────────────────────────────
with tab_pack:
    st.markdown("### 📦 Live Sourcing & Packaging Calculator")

    # Gunakan reset_counter sebagai suffix key agar widget benar-benar reset
    rc = st.session_state.reset_counter

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            pricing_commodity = st.selectbox(
                "Select Commodity",
                list(PACKAGING_MASTER.keys()),
                index=None,
                placeholder="-",
                key=f"pricing_commodity_{rc}"
            )

        with col2:
            pricing_volume = st.number_input(
                "Volume Target (Kg)",
                min_value=1.0,
                step=50.0,
                value=None,
                placeholder="-",
                key=f"pricing_volume_{rc}"
            )

        with col3:
            if pricing_commodity:
                available_packs = list(PACKAGING_MASTER[pricing_commodity].keys())
                pricing_pack = st.selectbox(
                    "Select Packaging Type",
                    available_packs,
                    index=None,
                    placeholder="-",
                    key=f"pricing_pack_{rc}"
                )
            else:
                st.selectbox("Select Packaging Type", [], disabled=True, placeholder="-", key=f"pricing_pack_disabled_{rc}")
                pricing_pack = None

    if pricing_commodity and pricing_volume and pricing_pack:
        calc_result = calculate_packaging_cost(
            pricing_commodity, pricing_volume, pricing_pack,
            exchange_rate=live_rate
        )

        if "error" not in calc_result:
            st.markdown("---")

            st.markdown("##### 📦 Logistics & Weight Specifications")
            weight_col1, weight_col2, weight_col3 = st.columns(3)

            with weight_col1:
                st.metric(
                    label="Total Units Needed",
                    value=f"{calc_result['total_units_needed']:,} {calc_result['packaging_type']}(s)"
                )
            with weight_col2:
                st.metric(
                    label="Estimated Net Weight",
                    value=f"{calc_result['net_weight_kg']:,} Kg"
                )
            with weight_col3:
                st.metric(
                    label="Estimated Gross Weight",
                    value=f"{calc_result['gross_weight_kg']:,} Kg",
                    delta=f"+{calc_result['gross_weight_kg'] - calc_result['net_weight_kg']:.2f} Kg Tare"
                )

            st.markdown(" ")

            st.markdown("##### 💵 Commercial Packaging Cost (USD)")
            cost_col1, cost_col2 = st.columns(2)

            with cost_col1:
                st.metric(
                    label="Total Packaging Cost (USD)",
                    value=f"$ {calc_result['total_packaging_cost_usd']:,}"
                )
            with cost_col2:
                st.metric(
                    label="Packaging Cost/Kg (USD)",
                    value=f"$ {calc_result['packaging_cost_per_kg_usd']:,}/Kg"
                )

            st.info(
                f"💡 **Formula Breakdown:** \n"
                f"• Unit Price: IDR {calc_result['price_per_unit_idr']:,}/{calc_result['packaging_type']}  \n"
                f"• Total Cost in Local Currency: {calc_result['total_units_needed']:,} units × IDR {calc_result['price_per_unit_idr']:,} = IDR {calc_result['total_units_needed'] * calc_result['price_per_unit_idr']:,}  \n"
                f"• Exchange Rate: USD 1 = IDR {calc_result['exchange_rate']:,}  \n"
                f"• USD Result: IDR {calc_result['total_units_needed'] * calc_result['price_per_unit_idr']:,} ÷ IDR {calc_result['exchange_rate']:,} = **USD {calc_result['total_packaging_cost_usd']:,}**"
            )

            st.session_state.current_calc_context = (
                f"User calculated Sourcing {pricing_volume} kg of {pricing_commodity} packed in {pricing_pack}. "
                f"Logistics Specs: Needs {calc_result['total_units_needed']} units. Net Weight: {calc_result['net_weight_kg']} Kg, Gross Weight: {calc_result['gross_weight_kg']} Kg. "
                f"Commercial Pricing: Total Cost USD $ {calc_result['total_packaging_cost_usd']:,} ($ {calc_result['packaging_cost_per_kg_usd']:,}/Kg)."
            )

            # ── AUTO-SYNC ke Tab FOB ──────────────────────────────────
            # Petakan nama komoditas Sourcing → nama komoditas FOB
            COMMODITY_MAP_TO_FOB = {
                "Cassia Whole":   "Cassia Whole",
                "Cassia Powder":  "Cassia Powder",
                "Black Pepper":   "Black Pepper (Whole)",
                "White Pepper":   "White Pepper (Whole)",
                "Clove":          "Clove",
                "Nutmeg":         "Nutmeg",
                "Vanilla":        "Vanilla",
                "Patchouli Oil":  "Patchouli Oil",
            }
            # Petakan nama packaging Sourcing → nama packaging FOB
            PACKAGING_MAP_TO_FOB = {
                "PP Woven Bag 25 Kg":        "PP Woven Bag 25 Kg",
                "PP Woven Bag 50 Kg":        "PP Woven Bag 50 Kg",
                "Kraft Paper Bag 20 Kg":     "Kraft Paper Bag 20 Kg",
                "Kraft Paper Bag 25 Kg":     "Kraft Paper Bag 25 Kg",
                "Vacuum Bag + Carton 5 Kg":  "Vacuum Bag + Carton 5 Kg",
                "Vacuum Bag + Carton 10 Kg": "Vacuum Bag + Carton 10 Kg",
                "HDPE Drum 25 Kg":           "HDPE Drum 25 Kg",
                "Steel Drum 180 Kg":         "Steel Drum 180 Kg",
            }
            st.session_state.sync_commodity = COMMODITY_MAP_TO_FOB.get(pricing_commodity)
            st.session_state.sync_volume    = float(pricing_volume)
            st.session_state.sync_packaging = PACKAGING_MAP_TO_FOB.get(pricing_pack, "PP Woven Bag 25 Kg")
            st.session_state.sync_applied   = False

            st.success(
                f"✅ Data synced to **🚢 FOB Commercial Calculator** tab — "
                f"commodity, volume, and packaging have been pre-filled."
            )
    else:
        st.markdown(
            "<p style='color: #888; font-style: italic; padding-top: 10px;'>"
            "ℹ️ Please select a commodity, target volume, and packaging type to generate the live quotation estimate."
            "</p>",
            unsafe_allow_html=True
        )
        st.session_state.current_calc_context = "No active calculation on screen."

# ── TAB 2: FOB CALCULATOR ─────────────────────────────────────────────────
with tab_fob:
    st.subheader("🚢 Live FOB Commercial Calculator")

    # ── Baca nilai sync dari Tab Sourcing ─────────────────────────────────
    synced_commodity  = st.session_state.get("sync_commodity")
    synced_volume     = st.session_state.get("sync_volume")
    synced_packaging  = st.session_state.get("sync_packaging")

    rc = st.session_state.reset_counter

    # ── KUNCI SOLUSI SYNC: inject langsung ke session_state widget key ────
    # Streamlit membaca nilai widget dari st.session_state[key].
    # Jika kita set nilainya SEBELUM widget dirender, widget akan tampil
    # dengan nilai tersebut — ini cara resmi mengatasi "index diabaikan".
    fob_commodity_list = list(COMMODITY_FOB_MASTER.keys())
    fob_pack_list = [
        "PP Woven Bag 25 Kg",
        "PP Woven Bag 50 Kg",
        "Kraft Paper Bag 20 Kg",
        "Kraft Paper Bag 25 Kg",
        "Vacuum Bag + Carton 5 Kg",
        "Vacuum Bag + Carton 10 Kg",
        "HDPE Drum 25 Kg",
        "Steel Drum 180 Kg"
    ]

    if not st.session_state.get("sync_applied", True) and synced_commodity:
        if synced_commodity in fob_commodity_list:
            st.session_state[f"fob_commodity_{rc}"] = synced_commodity
        if synced_volume:
            st.session_state[f"fob_volume_{rc}"] = synced_volume
        if synced_packaging and synced_packaging in fob_pack_list:
            st.session_state[f"fob_packaging_{rc}"] = synced_packaging
        st.session_state.sync_applied = True

    # Tampilkan banner jika ada data sync masuk
    if synced_commodity:
        st.info(
            f"🔗 **Auto-filled from Sourcing & Packaging Calculator** — "
            f"Commodity: **{synced_commodity}** | Volume: **{synced_volume:,} Kg** | "
            f"Packaging: **{synced_packaging}**. You may adjust any field before calculating."
        )

    with st.container(border=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            commodity = st.selectbox(
                "Commodity",
                fob_commodity_list,
                index=None,
                placeholder="-",
                key=f"fob_commodity_{rc}"
            )
            volume_kg = st.number_input(
                "Volume (Kg)",
                min_value=1.0,
                value=None,
                placeholder="-",
                key=f"fob_volume_{rc}"
            )
        with col_f2:
            packaging_type = st.selectbox(
                "Packaging Type",
                fob_pack_list,
                index=None,
                placeholder="-",
                key=f"fob_packaging_{rc}"
            )
            loading_port = st.selectbox(
                "Loading Port",
                list(DOMESTIC_FREIGHT_COST_IDR.keys()),
                index=None,
                placeholder="-",
                key=f"fob_port_{rc}"
            )

        exchange_rate = st.number_input(
            "USD/IDR Exchange Rate",
            min_value=1,
            value=live_rate,
            key=f"fob_exrate_{rc}"
        )
        if live_rate_ok:
            st.caption(
                f"🟢 **Live rate** · USD 1 = IDR {live_rate:,} "
                f"· Source: open.er-api.com · Updated: {live_rate_updated} UTC"
            )
        else:
            st.caption("🟡 **Fallback rate** · Live fetch unavailable — using IDR 17,500")

    btn_col1, btn_col2 = st.columns([3, 1])
    with btn_col1:
        calc_btn = st.button("⚙️ Calculate FOB", use_container_width=True, type="primary")
    with btn_col2:
        reset_btn = st.button("🔄 Reset", use_container_width=True)

    # ── PRIORITY 2: RESET BUTTON — reset SEMUA tab ───────────────────────
    if reset_btn:
        st.session_state.fob_result = None
        st.session_state.fob_error  = None
        st.session_state.current_calc_context = "No active calculation on screen."
        # Reset sync keys (Tab Sourcing → Tab FOB)
        st.session_state.sync_commodity = None
        st.session_state.sync_volume    = None
        st.session_state.sync_packaging = None
        st.session_state.sync_applied   = True
        # Increment counter → widget keys berubah → semua widget kembali ke default
        st.session_state.reset_counter += 1
        st.rerun()

    # ── PRIORITY 1: CALCULATE & SIMPAN KE SESSION STATE ──────────────────
    if calc_btn:
        if not commodity or not volume_kg or not packaging_type or not loading_port:
            st.warning("⚠️ Please fill in all fields before calculating.")
        else:
            raw_result = calculate_fob_price(
                commodity_name=commodity,
                volume_kg=volume_kg,
                packaging_type=packaging_type,
                loading_port=loading_port,
                exchange_rate=exchange_rate
            )
            if "error" in raw_result:
                st.session_state.fob_result = None
                st.session_state.fob_error = raw_result["error"]
            else:
                st.session_state.fob_result = raw_result
                st.session_state.fob_error = None
                st.session_state.current_calc_context = (
                    f"ACTIVE FOB CALCULATION:\n"
                    f"- Commodity: {raw_result['commodity']} (HS Code: {raw_result['hs_code']})\n"
                    f"- Origin: {raw_result['origin']}\n"
                    f"- Volume: {raw_result['volume_kg']} Kg (Net), {raw_result['gross_weight_kg']} Kg (Gross)\n"
                    f"- Packaging: {packaging_type} — {raw_result['total_units_needed']} unit(s)\n"
                    f"- Loading Port: {raw_result['loading_port']}\n"
                    f"- Exchange Rate: USD 1 = IDR {raw_result['exchange_rate']:,}\n"
                    f"- FOB Price/Kg: USD {raw_result['fob_price_per_kg']:.4f}\n"
                    f"- FOB Total Value: USD {raw_result['fob_total_usd']:,.2f}\n"
                    f"- Total Cost: USD {raw_result['total_cost_usd']:,.2f}\n"
                    f"- Profit: USD {raw_result['profit_usd']:,.2f}\n"
                    f"- Margin: {raw_result['margin_percent']}%\n"
                    f"- Cost Breakdown per Kg (IDR): "
                    f"Raw Material={raw_result['breakdown_per_kg']['raw_material_idr']:,}, "
                    f"Processing={raw_result['breakdown_per_kg']['processing_idr']:,}, "
                    f"Packaging={raw_result['breakdown_per_kg']['packaging_idr']:,}, "
                    f"Freight={raw_result['breakdown_per_kg']['freight_idr']:,}, "
                    f"Documentation={raw_result['breakdown_per_kg']['documentation_idr']:,}, "
                    f"Port Handling={raw_result['breakdown_per_kg']['port_handling_idr']:,}"
                )

    # ── RENDER HASIL ──────────────────────────────────────────────────────
    if st.session_state.get("fob_error"):
        st.error(st.session_state.fob_error)

    elif st.session_state.get("fob_result"):
        result = st.session_state.fob_result
        st.markdown("---")

        # ── FOB PRICING: 2 baris agar tidak terpotong (Fix #4) ──────────
        st.markdown("### 📊 FOB Pricing")

        # Baris atas: 3 metrik utama (nilai besar)
        row1_c1, row1_c2, row1_c3 = st.columns(3)
        with row1_c1:
            st.metric(label="FOB Price / Kg (USD)",
                      value=f"${result['fob_price_per_kg']:.4f}")
        with row1_c2:
            # Format kompak: pisah ribuan dengan koma, tanpa pecahan berlebihan
            fob_total_display = f"${result['fob_total_usd']:,.2f}"
            st.metric(label="FOB Total Value (USD)", value=fob_total_display)
        with row1_c3:
            st.metric(label="Total Cost (USD)",
                      value=f"${result['total_cost_usd']:,.2f}")

        # Baris bawah: Profit & Margin
        row2_c1, row2_c2, row2_c3 = st.columns(3)
        with row2_c1:
            st.metric(label="Profit (USD)",
                      value=f"${result['profit_usd']:,.2f}")
        with row2_c2:
            st.metric(label="Margin", value=f"{result['margin_percent']}%")
        with row2_c3:
            st.metric(label="Exchange Rate",
                      value=f"IDR {result['exchange_rate']:,}")

        st.markdown(" ")

        # ── FOB VALIDATION BOX ────────────────────────────────────────
        st.success(
            f"**FOB Calculation Validation**\n\n"
            f"Total Cost &nbsp;&nbsp;&nbsp;&nbsp; **USD {result['total_cost_usd']:,.2f}**\n\n"
            f"Margin &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; **{result['margin_percent']}%**\n\n"
            f"Profit &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; **USD {result['profit_usd']:,.2f}**\n\n"
            f"✅ &nbsp;FOB calculation completed successfully."
        )

        st.markdown(" ")

        # ── SHIPMENT INFORMATION ──────────────────────────────────────
        st.markdown("### 🚢 Shipment Information")
        st.write(f"**Commodity:** {result['commodity']}")
        st.write(f"**HS Code:** {result['hs_code']}")
        st.write(f"**Origin:** {result['origin']}")
        st.write(f"**Loading Port:** {result['loading_port']}")
        st.write(f"**Net Weight:** {result['net_weight_kg']:,} Kg")
        st.write(f"**Gross Weight:** {result['gross_weight_kg']:,} Kg")
        st.write(f"**Total Packaging Units:** {result['total_units_needed']:,}")

        st.markdown(" ")

        # ── COST BREAKDOWN ────────────────────────────────────────────
        st.markdown("### 🔍 Cost Breakdown (IDR & USD)")
        breakdown = result["breakdown_total"]
        er = result.get("exchange_rate", 17500)

        breakdown_rows = []
        for key, idr_val in breakdown.items():
            label = key.replace("_idr", "").replace("_", " ").title()
            usd_val = idr_val / er
            pct = (idr_val / sum(breakdown.values()) * 100) if sum(breakdown.values()) > 0 else 0
            breakdown_rows.append({
                "Cost Component": label,
                "IDR": f"Rp {idr_val:,.0f}",
                "USD": f"${usd_val:,.2f}",
                "Share (%)": f"{pct:.1f}%"
            })
        import pandas as pd
        df_breakdown = pd.DataFrame(breakdown_rows)
        st.dataframe(df_breakdown, use_container_width=True, hide_index=True)

# ── TAB 3: PROFORMA INVOICE GENERATOR ────────────────────────────────────
with tab_pi:
    st.subheader("📄 Live PI Generator")

    fob_data = st.session_state.get("fob_result")

    if not fob_data:
        st.info(
            "ℹ️ No active FOB calculation found. "
            "Please complete a FOB calculation in the **🚢 FOB Commercial Calculator** tab first, "
            "then return here to generate your Proforma Invoice."
        )
    else:
        st.success(
            f"✅ FOB data loaded: **{fob_data['commodity']}** — "
            f"{fob_data['volume_kg']:,} Kg @ USD {fob_data['fob_price_per_kg']:.4f}/Kg "
            f"| Total: **USD {fob_data['fob_total_usd']:,.2f}**"
        )

        st.markdown("---")

        # ── SELLER & BUYER ────────────────────────────────────────
        st.markdown("#### 🏢 Seller & Buyer Information")

        # ── Daftar negara lengkap (ISO 3166-1) ───────────────────────────
        COUNTRY_LIST = [
            "Afghanistan", "Albania", "Algeria", "Andorra", "Angola",
            "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
            "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados",
            "Belarus", "Belgium", "Belize", "Benin", "Bhutan",
            "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei",
            "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia",
            "Cameroon", "Canada", "Central African Republic", "Chad", "Chile",
            "China", "Colombia", "Comoros", "Congo (Brazzaville)", "Congo (Kinshasa)",
            "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czech Republic",
            "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador",
            "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia",
            "Eswatini", "Ethiopia", "Fiji", "Finland", "France",
            "Gabon", "Gambia", "Georgia", "Germany", "Ghana",
            "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau",
            "Guyana", "Haiti", "Honduras", "Hungary", "Iceland",
            "India", "Indonesia", "Iran", "Iraq", "Ireland",
            "Israel", "Italy", "Jamaica", "Japan", "Jordan",
            "Kazakhstan", "Kenya", "Kiribati", "Kuwait", "Kyrgyzstan",
            "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia",
            "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar",
            "Malawi", "Malaysia", "Maldives", "Mali", "Malta",
            "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia",
            "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco",
            "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal",
            "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria",
            "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan",
            "Palau", "Palestine", "Panama", "Papua New Guinea", "Paraguay",
            "Peru", "Philippines", "Poland", "Portugal", "Qatar",
            "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
            "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia",
            "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore",
            "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa",
            "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan",
            "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan",
            "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo",
            "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan",
            "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom",
            "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City",
            "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
        ]

        pi_col1, pi_col2 = st.columns(2)
        with pi_col1:
            st.markdown("**Seller**")
            seller_name    = st.text_input("Seller Name",    value="", placeholder="e.g. PT Magastu Indoprime Group")
            seller_address = st.text_input("Seller Address", value="", placeholder="e.g. Jakarta, Indonesia")
            seller_country = st.selectbox(
                "Seller Country",
                COUNTRY_LIST,
                index=COUNTRY_LIST.index("Indonesia"),
                key="seller_country_select"
            )
            seller_email   = st.text_input("Seller Email",   value="", placeholder="e.g. trade@magastu.id")
            seller_phone   = st.text_input("Seller Phone",   value="", placeholder="e.g. +62 21 XXXX XXXX")
        with pi_col2:
            st.markdown("**Buyer / Consignee**")
            buyer_name    = st.text_input("Buyer Name",    placeholder="e.g. Spice Trading GmbH")
            buyer_address = st.text_input("Buyer Address", placeholder="Full address")
            buyer_country = st.selectbox(
                "Buyer Country",
                COUNTRY_LIST,
                index=None,
                placeholder="- Select country -",
                key="buyer_country_select"
            )
            buyer_email   = st.text_input("Buyer Email",   placeholder="e.g. import@spicetrading.de")
            buyer_phone   = st.text_input("Buyer Phone",   placeholder="e.g. +49 40 XXXX XXXX")

        # ── COMMERCIAL TERMS ──────────────────────────────────────
        st.markdown("#### 📋 Commercial Terms")
        terms_col1, terms_col2, terms_col3 = st.columns(3)
        with terms_col1:
            payment_terms = st.selectbox(
                "Payment Terms",
                [
                    "100% T/T in Advance",
                    "50% T/T Advance, 50% Before Shipment",
                    "30% T/T Advance, 70% Against B/L Copy",
                    "Letter of Credit (L/C) at Sight",
                    "Letter of Credit (L/C) 30 Days",
                    "Letter of Credit (L/C) 60 Days",
                    "Documents Against Payment (D/P)"
                ]
            )
        with terms_col2:
            validity_days = st.number_input(
                "Price Validity (Days)", min_value=1, max_value=90, value=14
            )
        with terms_col3:
            pi_number = st.text_input(
                "PI Number",
                value=f"InTradeX-Mate/PI/{datetime.now().strftime('%d%b%Y').upper()}/000001"
            )

        # ── BANK DETAILS & NOTES ──────────────────────────────────
        st.markdown("#### 🏦 Bank Details & Notes")
        bank_col, notes_col = st.columns(2)
        with bank_col:
            bank_details = st.text_area(
                "Bank Details",
                placeholder=(
                    "Bank Name:\nAccount Name:\nAccount Number:\n"
                    "Swift / BIC Code:\nBank Address:"
                ),
                height=130
            )
        with notes_col:
            custom_notes = st.text_area(
                "Additional Notes (optional — leave blank for default)",
                placeholder="e.g. special handling instructions, certifications required...",
                height=130
            )

        # ── PACKAGING TYPE (dari FOB context) ────────────────────
        ctx = st.session_state.get("current_calc_context", "")
        if "Packaging:" in ctx:
            packaging_from_ctx = ctx.split("Packaging: ")[1].split("\n")[0].split(" —")[0].strip()
        else:
            packaging_from_ctx = "As per FOB calculation"

        st.markdown("---")

        # ── PI PREVIEW ────────────────────────────────────────────
        if buyer_name:
            st.markdown("#### 👁️ Proforma Invoice Preview")
            issue_date_prev = datetime.now().strftime("%d %B %Y")
            valid_prev = (datetime.now() + timedelta(days=int(validity_days))).strftime("%d %B %Y")
            with st.container(border=True):
                import pandas as _pd
                st.markdown(f"**PI:** `{pi_number}` &nbsp;&nbsp; **Issue:** {issue_date_prev} &nbsp;&nbsp; **Valid Until:** {valid_prev} ({validity_days} days)")
                st.markdown("---")
                prev_c1, prev_c2 = st.columns(2)
                with prev_c1:
                    st.markdown("**SELLER**")
                    st.markdown(f"{seller_name or '—'}  \n{seller_address or '—'}  \n{seller_country}  \n{seller_email or '—'}  \n{seller_phone or '—'}")
                with prev_c2:
                    st.markdown("**BUYER / CONSIGNEE**")
                    st.markdown(f"{buyer_name or '—'}  \n{buyer_address or '—'}  \n{buyer_country or '—'}  \n{buyer_email or '—'}  \n{buyer_phone or '—'}")
                st.markdown("---")
                st.markdown("**COMMODITY & PRICING**")
                _df_prev = _pd.DataFrame([{
                    "Commodity": fob_data['commodity'],
                    "HS Code": fob_data['hs_code'],
                    "Qty (Kg)": f"{fob_data['volume_kg']:,}",
                    "Unit Price (USD/Kg)": f"${fob_data['fob_price_per_kg']:.4f}",
                    "Total FOB (USD)": f"${fob_data['fob_total_usd']:,.2f}",
                    "Incoterm": f"FOB {fob_data['loading_port']}"
                }])
                st.dataframe(_df_prev, use_container_width=True, hide_index=True)
                st.markdown(f"**Payment Terms:** {payment_terms}")

        # ── FORMAT SELECTION ──────────────────────────────────────
        st.markdown("#### 📥 Download Format")
        pi_format = st.radio(
            "Select output format:",
            ["PDF", "DOCX (Word)"],
            horizontal=True,
            key="pi_format_radio"
        )

        # ── GENERATE BUTTON ───────────────────────────────────────
        st.markdown(" ")
        confirm_msg = CONFIRM_MESSAGES.get(lang_option, CONFIRM_MESSAGES["English"])
        st.info(f"🖨️ **{confirm_msg}**")

        if st.button("📄 Generate & Download Proforma Invoice",
                     use_container_width=True, type="primary"):
            if not buyer_name or not buyer_country:
                st.warning("⚠️ Please fill in at least Buyer Name and Buyer Country.")
            else:
                issue_date_str = datetime.now().strftime("%d %B %Y")

                if pi_format == "PDF":
                    with st.spinner("Generating PDF..."):
                        pdf_buf = generate_pi_pdf(
                            pi_number=pi_number,
                            issue_date_str=issue_date_str,
                            validity_days=validity_days,
                            seller_name=seller_name,
                            seller_address=seller_address,
                            seller_country=seller_country,
                            seller_email=seller_email,
                            seller_phone=seller_phone,
                            buyer_name=buyer_name,
                            buyer_address=buyer_address,
                            buyer_country=buyer_country,
                            buyer_email=buyer_email,
                            buyer_phone=buyer_phone,
                            fob_data=fob_data,
                            packaging_type=packaging_from_ctx,
                            payment_terms=payment_terms,
                            bank_details=bank_details,
                            notes=custom_notes,
                            lang=lang_option
                        )
                    st.success("✅ PDF ready! Click the button below to download.")
                    st.download_button(
                        label=f"⬇️ Download {pi_number}.pdf",
                        data=pdf_buf,
                        file_name=f"{pi_number}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

                else:  # DOCX
                    import subprocess, tempfile, os
                    valid_until_pi = (datetime.now() + timedelta(days=int(validity_days))).strftime("%d %B %Y")
                    bd_escaped = (bank_details or "—").replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
                    notes_escaped = (custom_notes or "—").replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
                    js_pi = f"""
const {{ Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, WidthType, ShadingType, BorderStyle }} = require('docx');
const fs = require('fs');

const DARK_GREEN = "1B5E20";
const MID_GREEN  = "2E7D32";
const LIGHT_GREEN = "E8F5E9";
const border = {{ style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }};
const borders = {{ top: border, bottom: border, left: border, right: border }};
const noBorder = {{ style: BorderStyle.NONE, size: 0, color: "FFFFFF" }};
const noBorders = {{ top: noBorder, bottom: noBorder, left: noBorder, right: noBorder }};

function hdrCell(text, w) {{
    return new TableCell({{
        borders, width: {{ size: w, type: WidthType.DXA }},
        shading: {{ fill: LIGHT_GREEN, type: ShadingType.CLEAR }},
        margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
        children: [new Paragraph({{ children: [new TextRun({{ text, bold: true, size: 18 }})] }})]
    }});
}}
function dataCell(text, w) {{
    return new TableCell({{
        borders, width: {{ size: w, type: WidthType.DXA }},
        margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
        children: [new Paragraph({{ children: [new TextRun({{ text, size: 18 }})] }})]
    }});
}}
function lbl(label, value, w1, w2) {{
    return [
        new TableCell({{ borders: noBorders, width: {{ size: w1, type: WidthType.DXA }},
            margins: {{ top: 40, bottom: 40, left: 60, right: 60 }},
            children: [new Paragraph({{ children: [new TextRun({{ text: label, bold: true, size: 18, color: DARK_GREEN }})] }})] }}),
        new TableCell({{ borders: noBorders, width: {{ size: w2, type: WidthType.DXA }},
            margins: {{ top: 40, bottom: 40, left: 60, right: 60 }},
            children: [new Paragraph({{ children: [new TextRun({{ text: value, size: 18 }})] }})] }})
    ];
}}

const doc = new Document({{
    sections: [{{
        properties: {{ page: {{ size: {{ width: 11906, height: 16838 }},
            margin: {{ top: 1080, right: 1080, bottom: 1080, left: 1080 }} }} }},
        children: [
            new Paragraph({{
                alignment: AlignmentType.CENTER,
                shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                spacing: {{ before: 0, after: 60 }},
                children: [new TextRun({{ text: "PROFORMA INVOICE", bold: true, size: 40, color: "FFFFFF" }})]
            }}),
            new Paragraph({{
                alignment: AlignmentType.CENTER,
                shading: {{ fill: MID_GREEN, type: ShadingType.CLEAR }},
                spacing: {{ before: 0, after: 160 }},
                children: [new TextRun({{ text: "InTradeX-Mate  |  A Strategic Initiative from MAGASTU  |  Indonesian Spice Export", size: 16, color: "FFFFFF" }})]
            }}),
            new Table({{
                width: {{ size: 9746, type: WidthType.DXA }},
                columnWidths: [2160, 7586],
                rows: [
                    new TableRow({{ children: lbl("PI Number", "{pi_number}", 2160, 7586) }}),
                    new TableRow({{ children: lbl("Issue Date", "{issue_date_str}", 2160, 7586) }}),
                    new TableRow({{ children: lbl("Valid Until", "{valid_until_pi} ({validity_days} days)", 2160, 7586) }}),
                ]
            }}),
            new Paragraph({{ spacing: {{ before: 100, after: 100 }}, border: {{ bottom: {{ style: BorderStyle.SINGLE, size: 4, color: DARK_GREEN, space: 1 }} }}, children: [] }}),
            new Table({{
                width: {{ size: 9746, type: WidthType.DXA }},
                columnWidths: [4873, 4873],
                rows: [
                    new TableRow({{ children: [
                        new TableCell({{ borders, width: {{ size: 4873, type: WidthType.DXA }},
                            shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                            margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                            children: [new Paragraph({{ children: [new TextRun({{ text: "SELLER", bold: true, size: 18, color: "FFFFFF" }})] }})] }}),
                        new TableCell({{ borders, width: {{ size: 4873, type: WidthType.DXA }},
                            shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                            margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                            children: [new Paragraph({{ children: [new TextRun({{ text: "BUYER / CONSIGNEE", bold: true, size: 18, color: "FFFFFF" }})] }})] }}),
                    ]}}),
                    new TableRow({{ children: [
                        new TableCell({{ borders, width: {{ size: 4873, type: WidthType.DXA }},
                            margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                            children: [
                                new Paragraph({{ children: [new TextRun({{ text: "{seller_name or '—'}", size: 18 }})] }}),
                                new Paragraph({{ children: [new TextRun({{ text: "{seller_address or '—'}", size: 16, color: "555555" }})] }}),
                                new Paragraph({{ children: [new TextRun({{ text: "{seller_country}", size: 16, color: "555555" }})] }}),
                                new Paragraph({{ children: [new TextRun({{ text: "{seller_email or '—'}", size: 16, color: "555555" }})] }}),
                                new Paragraph({{ children: [new TextRun({{ text: "{seller_phone or '—'}", size: 16, color: "555555" }})] }}),
                            ] }}),
                        new TableCell({{ borders, width: {{ size: 4873, type: WidthType.DXA }},
                            margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                            children: [
                                new Paragraph({{ children: [new TextRun({{ text: "{buyer_name or '—'}", size: 18 }})] }}),
                                new Paragraph({{ children: [new TextRun({{ text: "{buyer_address or '—'}", size: 16, color: "555555" }})] }}),
                                new Paragraph({{ children: [new TextRun({{ text: "{str(buyer_country) if buyer_country else '—'}", size: 16, color: "555555" }})] }}),
                                new Paragraph({{ children: [new TextRun({{ text: "{buyer_email or '—'}", size: 16, color: "555555" }})] }}),
                                new Paragraph({{ children: [new TextRun({{ text: "{buyer_phone or '—'}", size: 16, color: "555555" }})] }}),
                            ] }}),
                    ]}}),
                ]
            }}),
            new Paragraph({{ spacing: {{ before: 160, after: 60 }}, children: [] }}),
            new Paragraph({{
                shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                spacing: {{ before: 0, after: 60 }},
                children: [new TextRun({{ text: "  COMMODITY & SHIPMENT DETAILS", bold: true, size: 18, color: "FFFFFF" }})]
            }}),
            new Table({{
                width: {{ size: 9746, type: WidthType.DXA }},
                columnWidths: [2160, 3440, 1440, 2706],
                rows: [
                    new TableRow({{ children: lbl("Commodity", "{fob_data['commodity']}", 2160, 3440).concat(lbl("HS Code", "{fob_data['hs_code']}", 1440, 2706)) }}),
                    new TableRow({{ children: lbl("Origin", "{fob_data['origin']}", 2160, 3440).concat(lbl("Loading Port", "{fob_data['loading_port']}", 1440, 2706)) }}),
                    new TableRow({{ children: lbl("Net Weight", "{fob_data['volume_kg']:,} Kg", 2160, 3440).concat(lbl("Gross Weight", "{fob_data.get('gross_weight_kg', '—')} Kg", 1440, 2706)) }}),
                    new TableRow({{ children: lbl("Packaging", "{packaging_from_ctx}", 2160, 3440).concat(lbl("Total Units", "{fob_data.get('total_units_needed', '—')}", 1440, 2706)) }}),
                ]
            }}),
            new Paragraph({{ spacing: {{ before: 160, after: 60 }}, children: [] }}),
            new Paragraph({{
                shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                spacing: {{ before: 0, after: 60 }},
                children: [new TextRun({{ text: "  PRICING (Incoterm: FOB {fob_data['loading_port']})", bold: true, size: 18, color: "FFFFFF" }})]
            }}),
            new Table({{
                width: {{ size: 9746, type: WidthType.DXA }},
                columnWidths: [3411, 1266, 1267, 1657, 2145],
                rows: [
                    new TableRow({{ children: [hdrCell("Description",3411), hdrCell("HS Code",1266), hdrCell("Qty (Kg)",1267), hdrCell("Unit Price (USD/Kg)",1657), hdrCell("Total (USD)",2145)] }}),
                    new TableRow({{ children: [dataCell("{fob_data['commodity']}",3411), dataCell("{fob_data['hs_code']}",1266), dataCell("{fob_data['volume_kg']:,}",1267), dataCell("${fob_data['fob_price_per_kg']:.4f}",1657), dataCell("${fob_data['fob_total_usd']:,.2f}",2145)] }}),
                    new TableRow({{ children: [
                        dataCell("",3411), dataCell("",1266), dataCell("",1267),
                        new TableCell({{ borders, width: {{ size: 1657, type: WidthType.DXA }}, margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                            children: [new Paragraph({{ children: [new TextRun({{ text: "TOTAL FOB VALUE", bold: true, size: 18, color: DARK_GREEN }})] }})] }}),
                        new TableCell({{ borders, width: {{ size: 2145, type: WidthType.DXA }}, margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                            children: [new Paragraph({{ children: [new TextRun({{ text: "USD {fob_data['fob_total_usd']:,.2f}", bold: true, size: 18, color: DARK_GREEN }})] }})] }}),
                    ]}}),
                ]
            }}),
            new Paragraph({{ spacing: {{ before: 160, after: 60 }}, children: [] }}),
            new Paragraph({{
                shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                spacing: {{ before: 0, after: 60 }},
                children: [new TextRun({{ text: "  PAYMENT TERMS", bold: true, size: 18, color: "FFFFFF" }})]
            }}),
            new Paragraph({{ spacing: {{ before: 40, after: 40 }}, children: [new TextRun({{ text: "{payment_terms}", size: 18 }})] }}),
            new Paragraph({{
                shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                spacing: {{ before: 120, after: 60 }},
                children: [new TextRun({{ text: "  BANK DETAILS", bold: true, size: 18, color: "FFFFFF" }})]
            }}),
            new Paragraph({{ spacing: {{ before: 40, after: 40 }}, children: [new TextRun({{ text: "{bd_escaped}", size: 18 }})] }}),
            new Paragraph({{
                shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                spacing: {{ before: 120, after: 60 }},
                children: [new TextRun({{ text: "  NOTES & CONDITIONS", bold: true, size: 18, color: "FFFFFF" }})]
            }}),
            new Paragraph({{ spacing: {{ before: 40, after: 120 }}, children: [new TextRun({{ text: "{notes_escaped}", size: 18 }})] }}),
            new Paragraph({{ spacing: {{ before: 200, after: 0 }}, border: {{ top: {{ style: BorderStyle.SINGLE, size: 4, color: DARK_GREEN, space: 1 }} }}, children: [] }}),
            new Paragraph({{
                alignment: AlignmentType.CENTER,
                children: [new TextRun({{ text: "Generated by InTradeX-Mate  |  {pi_number}  |  Issued: {issue_date_str}", size: 14, color: "888888" }})]
            }}),
        ]
    }}]
}});
Packer.toBuffer(doc).then(buf => {{ fs.writeFileSync('/tmp/pi_output.docx', buf); console.log('OK'); }});
"""
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                        f.write(js_pi)
                        js_path = f.name

                    with st.spinner("Generating DOCX..."):
                        result = subprocess.run(['node', js_path], capture_output=True, text=True, timeout=30)
                    os.unlink(js_path)

                    if result.returncode == 0 and os.path.exists('/tmp/pi_output.docx'):
                        with open('/tmp/pi_output.docx', 'rb') as f:
                            docx_bytes = f.read()
                        os.unlink('/tmp/pi_output.docx')
                        st.success("✅ DOCX ready! Click the button below to download.")
                        st.download_button(
                            label=f"⬇️ Download {pi_number}.docx",
                            data=docx_bytes,
                            file_name=f"{pi_number}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True
                        )
                    else:
                        st.error(f"DOCX generation failed. Please use PDF format instead.\n{result.stderr[:300]}")

# ── TAB 4: QUOTATION GENERATOR ───────────────────────────────────────────
with tab_qt:
    st.subheader("📋 FOB Quotation Generator")

    fob_data_qt = st.session_state.get("fob_result")

    if not fob_data_qt:
        st.info(
            "ℹ️ No active FOB calculation found. "
            "Please complete a FOB calculation in the **🚢 FOB Commercial Calculator** tab first, "
            "then return here to generate your Quotation."
        )
    else:
        st.success(
            f"✅ FOB data loaded: **{fob_data_qt['commodity']}** — "
            f"{fob_data_qt['volume_kg']:,} Kg @ USD {fob_data_qt['fob_price_per_kg']:.4f}/Kg "
            f"| Total: **USD {fob_data_qt['fob_total_usd']:,.2f}**"
        )
        st.markdown("---")

        # ── QUOTATION DETAILS ─────────────────────────────────────────
        st.markdown("#### 🏢 Quotation Parties")
        qt_col1, qt_col2 = st.columns(2)
        with qt_col1:
            qt_seller_name    = st.text_input("Your Company Name", placeholder="e.g. PT Magastu Indoprime Group", key="qt_seller_name")
            qt_seller_address = st.text_input("Your Address", placeholder="e.g. Jakarta, Indonesia", key="qt_seller_addr")
            qt_seller_email   = st.text_input("Your Email", placeholder="e.g. trade@magastu.id", key="qt_seller_email")
            qt_seller_phone   = st.text_input("Your Phone / WhatsApp", placeholder="e.g. +62 812 XXXX XXXX", key="qt_seller_phone")
        with qt_col2:
            qt_buyer_name    = st.text_input("Buyer / Recipient Name", placeholder="e.g. Spice Trading GmbH", key="qt_buyer_name")
            qt_buyer_company = st.text_input("Buyer Company", placeholder="e.g. GmbH, Ltd, Inc", key="qt_buyer_company")
            qt_buyer_email   = st.text_input("Buyer Email", placeholder="e.g. import@spicetrading.de", key="qt_buyer_email")
            qt_buyer_country = st.text_input("Buyer Country", placeholder="e.g. Germany", key="qt_buyer_country")

        st.markdown("#### 📋 Quotation Terms")
        qt_terms_col1, qt_terms_col2, qt_terms_col3 = st.columns(3)
        with qt_terms_col1:
            qt_payment = st.selectbox(
                "Payment Terms",
                [
                    "100% T/T in Advance",
                    "50% T/T Advance, 50% Before Shipment",
                    "30% T/T Advance, 70% Against B/L Copy",
                    "Letter of Credit (L/C) at Sight",
                    "Documents Against Payment (D/P)"
                ],
                key="qt_payment"
            )
        with qt_terms_col2:
            qt_validity = st.number_input("Price Validity (Days)", min_value=1, max_value=90, value=14, key="qt_validity")
        with qt_terms_col3:
            qt_number = st.text_input(
                "Quotation Number",
                value=f"InTradeX-Mate/QT/{datetime.now().strftime('%d%b%Y').upper()}/000001",
                key="qt_number"
            )

        qt_notes = st.text_area(
            "Additional Notes (optional)",
            placeholder="e.g. Minimum order quantity, lead time, certification details...",
            height=100,
            key="qt_notes"
        )

        st.markdown("---")

        # ── PREVIEW ───────────────────────────────────────────────────
        if qt_buyer_name:
            st.markdown("#### 👁️ Quotation Preview")
            issue_date_qt = datetime.now().strftime("%d %B %Y")
            valid_until_qt = (datetime.now() + timedelta(days=int(qt_validity))).strftime("%d %B %Y")

            with st.container(border=True):
                st.markdown(f"**QUOTATION** &nbsp;&nbsp; `{qt_number}`")
                st.markdown(f"**Issue Date:** {issue_date_qt} &nbsp;&nbsp; **Valid Until:** {valid_until_qt} ({qt_validity} days)")
                st.markdown("---")
                qt_p1, qt_p2 = st.columns(2)
                with qt_p1:
                    st.markdown("**FROM (Seller)**")
                    st.markdown(f"{qt_seller_name or '—'}")
                    st.markdown(f"{qt_seller_address or '—'}")
                    st.markdown(f"{qt_seller_email or '—'} | {qt_seller_phone or '—'}")
                with qt_p2:
                    st.markdown("**TO (Buyer)**")
                    st.markdown(f"{qt_buyer_name or '—'} — {qt_buyer_company or '—'}")
                    st.markdown(f"{qt_buyer_country or '—'}")
                    st.markdown(f"{qt_buyer_email or '—'}")
                st.markdown("---")
                st.markdown("**COMMODITY & PRICING**")
                import pandas as pd
                qt_preview_df = pd.DataFrame([{
                    "Commodity": fob_data_qt['commodity'],
                    "HS Code": fob_data_qt['hs_code'],
                    "Origin": fob_data_qt['origin'],
                    "Volume (Kg)": f"{fob_data_qt['volume_kg']:,}",
                    "Unit Price (USD/Kg)": f"${fob_data_qt['fob_price_per_kg']:.4f}",
                    "Total FOB Value (USD)": f"${fob_data_qt['fob_total_usd']:,.2f}",
                    "Incoterm": f"FOB {fob_data_qt['loading_port']}"
                }])
                st.dataframe(qt_preview_df, use_container_width=True, hide_index=True)
                st.markdown(f"**Payment Terms:** {qt_payment}")
                if qt_notes:
                    st.markdown(f"**Notes:** {qt_notes}")

        # ── FORMAT SELECTION & GENERATE ───────────────────────────────
        st.markdown("#### 📥 Download Quotation")
        qt_format = st.radio(
            "Select output format:",
            ["PDF", "DOCX (Word)"],
            horizontal=True,
            key="qt_format"
        )

        st.info(f"🖨️ Review the preview above, then click Generate to download your Quotation.")

        if st.button("📄 Generate & Download Quotation", use_container_width=True, type="primary", key="qt_generate_btn"):
            if not qt_buyer_name:
                st.warning("⚠️ Please fill in at least the Buyer Name.")
            else:
                issue_date_qt = datetime.now().strftime("%d %B %Y")
                valid_until_qt = (datetime.now() + timedelta(days=int(qt_validity))).strftime("%d %B %Y")

                if qt_format == "PDF":
                    try:
                        from reportlab.lib.pagesizes import A4
                        from reportlab.lib import colors
                        from reportlab.lib.units import cm
                        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
                        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
                        import io

                        buf = io.BytesIO()
                        doc = SimpleDocTemplate(
                            buf, pagesize=A4,
                            leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm
                        )

                        styles = getSampleStyleSheet()
                        DARK_GREEN = colors.HexColor("#1B5E20")
                        MID_GREEN  = colors.HexColor("#2E7D32")
                        LIGHT_GREEN= colors.HexColor("#E8F5E9")
                        GRAY_TEXT  = colors.HexColor("#555555")
                        WHITE      = colors.white

                        title_style = ParagraphStyle("Title", fontSize=20, fontName="Helvetica-Bold",
                                                     textColor=WHITE, alignment=TA_CENTER, spaceAfter=4)
                        sub_style   = ParagraphStyle("Sub",   fontSize=9,  fontName="Helvetica",
                                                     textColor=WHITE, alignment=TA_CENTER)
                        body_style  = ParagraphStyle("Body",  fontSize=9,  fontName="Helvetica",
                                                     textColor=colors.black, leading=13)
                        label_style = ParagraphStyle("Label", fontSize=8,  fontName="Helvetica-Bold",
                                                     textColor=GRAY_TEXT)
                        small_style = ParagraphStyle("Small", fontSize=8,  fontName="Helvetica",
                                                     textColor=GRAY_TEXT)

                        story = []
                        page_w = A4[0] - 3.6*cm

                        # ── HEADER ──
                        header_data = [[
                            Paragraph("QUOTATION", title_style),
                        ]]
                        header_sub = [[
                            Paragraph(
                                "InTradeX-Mate &nbsp;|&nbsp; A Strategic Initiative from MAGASTU &nbsp;|&nbsp; Indonesian Spice Export",
                                sub_style
                            )
                        ]]
                        header_tbl = Table([[Paragraph("QUOTATION", title_style)]], colWidths=[page_w])
                        header_tbl.setStyle(TableStyle([
                            ("BACKGROUND", (0,0), (-1,-1), DARK_GREEN),
                            ("TOPPADDING", (0,0), (-1,-1), 10),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                        ]))
                        story.append(header_tbl)

                        sub_tbl = Table([[Paragraph(
                            "InTradeX-Mate  |  A Strategic Initiative from MAGASTU  |  Indonesian Spice Export",
                            sub_style
                        )]], colWidths=[page_w])
                        sub_tbl.setStyle(TableStyle([
                            ("BACKGROUND", (0,0), (-1,-1), MID_GREEN),
                            ("TOPPADDING", (0,0), (-1,-1), 4),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
                        ]))
                        story.append(sub_tbl)
                        story.append(Spacer(1, 0.3*cm))

                        # ── QT NUMBER / DATE / VALIDITY ──
                        meta_data = [
                            ["QT Number", qt_number, "Issue Date", issue_date_qt],
                            ["Valid Until", f"{valid_until_qt} ({qt_validity} days)", "", ""]
                        ]
                        meta_tbl = Table(meta_data, colWidths=[3*cm, 8*cm, 2.5*cm, 4.5*cm])
                        meta_tbl.setStyle(TableStyle([
                            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
                            ("FONTSIZE", (0,0), (-1,-1), 9),
                            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
                            ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
                            ("TEXTCOLOR", (0,0), (0,-1), DARK_GREEN),
                            ("TEXTCOLOR", (2,0), (2,-1), DARK_GREEN),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                        ]))
                        story.append(meta_tbl)
                        story.append(Spacer(1, 0.2*cm))
                        story.append(HRFlowable(width="100%", thickness=0.5, color=DARK_GREEN))
                        story.append(Spacer(1, 0.2*cm))

                        # ── SELLER / BUYER ──
                        half = page_w / 2
                        seller_block = [
                            Paragraph("SELLER", ParagraphStyle("SH", fontSize=9, fontName="Helvetica-Bold",
                                                               textColor=WHITE, backColor=DARK_GREEN,
                                                               leftIndent=4, rightIndent=4, spaceAfter=4)),
                            Paragraph(f"Company Name", label_style),
                            Paragraph(qt_seller_name or "—", body_style),
                            Paragraph(f"Address", label_style),
                            Paragraph(qt_seller_address or "—", body_style),
                            Paragraph("Country", label_style),
                            Paragraph("Indonesia", body_style),
                            Paragraph("Email", label_style),
                            Paragraph(qt_seller_email or "—", body_style),
                            Paragraph("Phone / WhatsApp", label_style),
                            Paragraph(qt_seller_phone or "—", body_style),
                        ]
                        buyer_block = [
                            Paragraph("BUYER / RECIPIENT", ParagraphStyle("BH", fontSize=9, fontName="Helvetica-Bold",
                                                                           textColor=WHITE, backColor=DARK_GREEN,
                                                                           leftIndent=4, rightIndent=4, spaceAfter=4)),
                            Paragraph("Company Name", label_style),
                            Paragraph(f"{qt_buyer_name or '—'} {qt_buyer_company or ''}", body_style),
                            Paragraph("Country", label_style),
                            Paragraph(qt_buyer_country or "—", body_style),
                            Paragraph("Email", label_style),
                            Paragraph(qt_buyer_email or "—", body_style),
                        ]

                        from reportlab.platypus import KeepInFrame
                        party_tbl = Table([[seller_block, buyer_block]], colWidths=[half, half])
                        party_tbl.setStyle(TableStyle([
                            ("VALIGN", (0,0), (-1,-1), "TOP"),
                            ("LEFTPADDING", (0,0), (-1,-1), 4),
                            ("RIGHTPADDING", (0,0), (-1,-1), 4),
                            ("BOX", (0,0), (0,0), 0.5, colors.HexColor("#CCCCCC")),
                            ("BOX", (1,0), (1,0), 0.5, colors.HexColor("#CCCCCC")),
                        ]))
                        story.append(party_tbl)
                        story.append(Spacer(1, 0.3*cm))

                        # ── COMMODITY & PRICING TABLE ──
                        sec_hdr = Table([[Paragraph("COMMODITY & PRICING DETAILS", ParagraphStyle(
                            "SecH", fontSize=9, fontName="Helvetica-Bold", textColor=WHITE
                        ))]], colWidths=[page_w])
                        sec_hdr.setStyle(TableStyle([
                            ("BACKGROUND", (0,0), (-1,-1), DARK_GREEN),
                            ("TOPPADDING", (0,0), (-1,-1), 4),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                            ("LEFTPADDING", (0,0), (-1,-1), 6),
                        ]))
                        story.append(sec_hdr)

                        price_hdr = ["Description", "HS Code", "Qty (Kg)", "Unit Price\n(USD/Kg)", "Total (USD)"]
                        price_row = [
                            fob_data_qt['commodity'],
                            fob_data_qt['hs_code'],
                            f"{fob_data_qt['volume_kg']:,}",
                            f"${fob_data_qt['fob_price_per_kg']:.4f}",
                            f"${fob_data_qt['fob_total_usd']:,.2f}"
                        ]
                        total_row = ["", "", "", "TOTAL FOB VALUE", f"${fob_data_qt['fob_total_usd']:,.2f}"]

                        col_w = [page_w*0.35, page_w*0.13, page_w*0.13, page_w*0.17, page_w*0.22]
                        price_tbl = Table([price_hdr, price_row, total_row], colWidths=col_w)
                        price_tbl.setStyle(TableStyle([
                            ("BACKGROUND", (0,0), (-1,0), LIGHT_GREEN),
                            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                            ("FONTSIZE", (0,0), (-1,-1), 9),
                            ("FONTNAME", (3,2), (-1,2), "Helvetica-Bold"),
                            ("TEXTCOLOR", (3,2), (-1,2), DARK_GREEN),
                            ("ALIGN", (2,0), (-1,-1), "RIGHT"),
                            ("GRID", (0,0), (-1,1), 0.5, colors.HexColor("#CCCCCC")),
                            ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
                            ("TOPPADDING", (0,0), (-1,-1), 4),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                            ("LEFTPADDING", (0,0), (-1,-1), 5),
                        ]))
                        story.append(price_tbl)
                        story.append(Spacer(1, 0.3*cm))

                        # ── INCOTERM / PORT / ORIGIN ──
                        ship_data = [
                            ["Incoterm", f"FOB {fob_data_qt['loading_port']}", "Origin", fob_data_qt['origin']],
                            ["Net Weight", f"{fob_data_qt['volume_kg']:,} Kg",
                             "Gross Weight", f"{fob_data_qt.get('gross_weight_kg', '—')} Kg"],
                            ["Payment Terms", qt_payment, "Price Validity", f"{valid_until_qt} ({qt_validity} days)"],
                        ]
                        ship_tbl = Table(ship_data, colWidths=[3*cm, 8*cm, 2.5*cm, 4.5*cm])
                        ship_tbl.setStyle(TableStyle([
                            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
                            ("FONTSIZE", (0,0), (-1,-1), 9),
                            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
                            ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
                            ("TEXTCOLOR", (0,0), (0,-1), DARK_GREEN),
                            ("TEXTCOLOR", (2,0), (2,-1), DARK_GREEN),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#EEEEEE")),
                        ]))
                        story.append(ship_tbl)

                        # ── NOTES ──
                        if qt_notes:
                            story.append(Spacer(1, 0.2*cm))
                            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC")))
                            story.append(Spacer(1, 0.1*cm))
                            story.append(Paragraph("Notes & Conditions", ParagraphStyle(
                                "NH", fontSize=9, fontName="Helvetica-Bold", textColor=DARK_GREEN)))
                            story.append(Paragraph(qt_notes, body_style))

                        # ── FOOTER ──
                        story.append(Spacer(1, 0.5*cm))
                        story.append(HRFlowable(width="100%", thickness=0.5, color=DARK_GREEN))
                        story.append(Spacer(1, 0.1*cm))
                        story.append(Paragraph(
                            f"Generated by InTradeX-Mate  |  {qt_number}  |  Issued: {issue_date_qt}",
                            ParagraphStyle("Footer", fontSize=7, fontName="Helvetica",
                                           textColor=GRAY_TEXT, alignment=TA_CENTER)
                        ))

                        doc.build(story)
                        buf.seek(0)

                        st.success("✅ Quotation PDF ready! Click below to download.")
                        st.download_button(
                            label=f"⬇️ Download {qt_number}.pdf",
                            data=buf,
                            file_name=f"{qt_number}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="qt_dl_pdf"
                        )
                    except Exception as e:
                        st.error(f"PDF generation error: {str(e)}")

                else:  # DOCX
                    try:
                        import subprocess, tempfile, os, io
                        # Write a Node.js script and run it
                        js_script = f"""
const {{ Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, WidthType, ShadingType, BorderStyle, VerticalAlign,
        HeadingLevel }} = require('docx');
const fs = require('fs');

const DARK_GREEN = "1B5E20";
const LIGHT_GREEN = "E8F5E9";
const border = {{ style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }};
const borders = {{ top: border, bottom: border, left: border, right: border }};
const noBorder = {{ style: BorderStyle.NONE, size: 0, color: "FFFFFF" }};
const noBorders = {{ top: noBorder, bottom: noBorder, left: noBorder, right: noBorder }};

function hdrCell(text, w) {{
    return new TableCell({{
        borders,
        width: {{ size: w, type: WidthType.DXA }},
        shading: {{ fill: LIGHT_GREEN, type: ShadingType.CLEAR }},
        margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
        children: [new Paragraph({{ children: [new TextRun({{ text, bold: true, size: 18 }})] }})]
    }});
}}
function dataCell(text, w) {{
    return new TableCell({{
        borders,
        width: {{ size: w, type: WidthType.DXA }},
        margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
        children: [new Paragraph({{ children: [new TextRun({{ text, size: 18 }})] }})]
    }});
}}
function labelCell(label, value, w1, w2) {{
    return [
        new TableCell({{
            borders: noBorders,
            width: {{ size: w1, type: WidthType.DXA }},
            margins: {{ top: 40, bottom: 40, left: 60, right: 60 }},
            children: [new Paragraph({{ children: [new TextRun({{ text: label, bold: true, size: 18, color: "1B5E20" }})] }})]
        }}),
        new TableCell({{
            borders: noBorders,
            width: {{ size: w2, type: WidthType.DXA }},
            margins: {{ top: 40, bottom: 40, left: 60, right: 60 }},
            children: [new Paragraph({{ children: [new TextRun({{ text: value, size: 18 }})] }})]
        }})
    ];
}}

const doc = new Document({{
    sections: [{{
        properties: {{ page: {{ size: {{ width: 11906, height: 16838 }}, margin: {{ top: 1080, right: 1080, bottom: 1080, left: 1080 }} }} }},
        children: [
            // TITLE
            new Paragraph({{
                alignment: AlignmentType.CENTER,
                shading: {{ fill: "1B5E20", type: ShadingType.CLEAR }},
                spacing: {{ before: 0, after: 60 }},
                children: [new TextRun({{ text: "QUOTATION", bold: true, size: 40, color: "FFFFFF" }})]
            }}),
            new Paragraph({{
                alignment: AlignmentType.CENTER,
                shading: {{ fill: "2E7D32", type: ShadingType.CLEAR }},
                spacing: {{ before: 0, after: 200 }},
                children: [new TextRun({{ text: "InTradeX-Mate  |  A Strategic Initiative from MAGASTU  |  Indonesian Spice Export", size: 16, color: "FFFFFF" }})]
            }}),

            // META
            new Table({{
                width: {{ size: 9746, type: WidthType.DXA }},
                columnWidths: [2160, 5040, 1440, 1106],
                rows: [
                    new TableRow({{ children: labelCell("QT Number", "{qt_number}", 2160, 7586) }}),
                    new TableRow({{ children: labelCell("Issue Date", "{issue_date_qt}", 2160, 3600).concat(labelCell("Valid Until", "{valid_until_qt} ({qt_validity} days)", 1440, 2546)) }}),
                ]
            }}),
            new Paragraph({{ spacing: {{ before: 100, after: 100 }}, border: {{ bottom: {{ style: BorderStyle.SINGLE, size: 4, color: "1B5E20", space: 1 }} }}, children: [] }}),

            // SELLER / BUYER
            new Table({{
                width: {{ size: 9746, type: WidthType.DXA }},
                columnWidths: [4873, 4873],
                rows: [
                    new TableRow({{
                        children: [
                            new TableCell({{ borders, width: {{ size: 4873, type: WidthType.DXA }},
                                shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                                margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                                children: [new Paragraph({{ children: [new TextRun({{ text: "SELLER", bold: true, size: 18, color: "FFFFFF" }})] }})] }}),
                            new TableCell({{ borders, width: {{ size: 4873, type: WidthType.DXA }},
                                shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                                margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                                children: [new Paragraph({{ children: [new TextRun({{ text: "BUYER / RECIPIENT", bold: true, size: 18, color: "FFFFFF" }})] }})] }}),
                        ]
                    }}),
                    new TableRow({{
                        children: [
                            new TableCell({{ borders, width: {{ size: 4873, type: WidthType.DXA }},
                                margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                                children: [
                                    new Paragraph({{ children: [new TextRun({{ text: "{qt_seller_name or '—'}", size: 18 }})] }}),
                                    new Paragraph({{ children: [new TextRun({{ text: "{qt_seller_address or '—'}", size: 16, color: "555555" }})] }}),
                                    new Paragraph({{ children: [new TextRun({{ text: "{qt_seller_email or '—'}", size: 16, color: "555555" }})] }}),
                                    new Paragraph({{ children: [new TextRun({{ text: "{qt_seller_phone or '—'}", size: 16, color: "555555" }})] }}),
                                ] }}),
                            new TableCell({{ borders, width: {{ size: 4873, type: WidthType.DXA }},
                                margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                                children: [
                                    new Paragraph({{ children: [new TextRun({{ text: "{qt_buyer_name or '—'}", size: 18 }})] }}),
                                    new Paragraph({{ children: [new TextRun({{ text: "{qt_buyer_company or '—'}", size: 16, color: "555555" }})] }}),
                                    new Paragraph({{ children: [new TextRun({{ text: "{qt_buyer_country or '—'}", size: 16, color: "555555" }})] }}),
                                    new Paragraph({{ children: [new TextRun({{ text: "{qt_buyer_email or '—'}", size: 16, color: "555555" }})] }}),
                                ] }}),
                        ]
                    }}),
                ]
            }}),
            new Paragraph({{ spacing: {{ before: 200, after: 80 }}, children: [] }}),

            // PRICING HEADER
            new Paragraph({{
                shading: {{ fill: DARK_GREEN, type: ShadingType.CLEAR }},
                spacing: {{ before: 0, after: 60 }},
                children: [new TextRun({{ text: "  COMMODITY & PRICING DETAILS", bold: true, size: 18, color: "FFFFFF" }})]
            }}),

            // PRICING TABLE
            new Table({{
                width: {{ size: 9746, type: WidthType.DXA }},
                columnWidths: [3411, 1266, 1267, 1657, 2145],
                rows: [
                    new TableRow({{ children: [
                        hdrCell("Description", 3411), hdrCell("HS Code", 1266),
                        hdrCell("Qty (Kg)", 1267), hdrCell("Unit Price\\n(USD/Kg)", 1657),
                        hdrCell("Total (USD)", 2145)
                    ]}}),
                    new TableRow({{ children: [
                        dataCell("{fob_data_qt['commodity']}", 3411),
                        dataCell("{fob_data_qt['hs_code']}", 1266),
                        dataCell("{fob_data_qt['volume_kg']:,}", 1267),
                        dataCell("${fob_data_qt['fob_price_per_kg']:.4f}", 1657),
                        dataCell("${fob_data_qt['fob_total_usd']:,.2f}", 2145)
                    ]}}),
                    new TableRow({{ children: [
                        dataCell("", 3411), dataCell("", 1266), dataCell("", 1267),
                        new TableCell({{ borders, width: {{ size: 1657, type: WidthType.DXA }},
                            margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                            children: [new Paragraph({{ children: [new TextRun({{ text: "TOTAL FOB VALUE", bold: true, size: 18, color: "1B5E20" }})] }})] }}),
                        new TableCell({{ borders, width: {{ size: 2145, type: WidthType.DXA }},
                            margins: {{ top: 60, bottom: 60, left: 80, right: 80 }},
                            children: [new Paragraph({{ children: [new TextRun({{ text: "${fob_data_qt['fob_total_usd']:,.2f}", bold: true, size: 18, color: "1B5E20" }})] }})] }}),
                    ]}}),
                ]
            }}),
            new Paragraph({{ spacing: {{ before: 160, after: 60 }}, children: [] }}),

            // SHIPMENT DETAILS
            new Table({{
                width: {{ size: 9746, type: WidthType.DXA }},
                columnWidths: [2160, 3440, 1440, 2706],
                rows: [
                    new TableRow({{ children: labelCell("Incoterm", "FOB {fob_data_qt['loading_port']}", 2160, 3440).concat(labelCell("Origin", "{fob_data_qt['origin']}", 1440, 2706)) }}),
                    new TableRow({{ children: labelCell("Payment Terms", "{qt_payment}", 2160, 3440).concat(labelCell("Valid Until", "{valid_until_qt}", 1440, 2706)) }}),
                ]
            }}),

            // NOTES
            {f'''new Paragraph({{ spacing: {{ before: 160, after: 40 }}, border: {{ top: {{ style: BorderStyle.SINGLE, size: 2, color: "CCCCCC", space: 1 }} }}, children: [] }}),
            new Paragraph({{ children: [new TextRun({{ text: "Notes & Conditions", bold: true, size: 18, color: "1B5E20" }})] }}),
            new Paragraph({{ children: [new TextRun({{ text: "{qt_notes}", size: 18 }})] }}),''' if qt_notes else ''}

            // FOOTER
            new Paragraph({{ spacing: {{ before: 300, after: 0 }}, border: {{ top: {{ style: BorderStyle.SINGLE, size: 4, color: "1B5E20", space: 1 }} }}, children: [] }}),
            new Paragraph({{
                alignment: AlignmentType.CENTER,
                children: [new TextRun({{ text: "Generated by InTradeX-Mate  |  {qt_number}  |  Issued: {issue_date_qt}", size: 14, color: "888888" }})]
            }}),
        ]
    }}]
}});

Packer.toBuffer(doc).then(buf => {{
    fs.writeFileSync('/tmp/quotation_output.docx', buf);
    console.log('OK');
}});
"""
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                            f.write(js_script)
                            js_path = f.name

                        result = subprocess.run(['node', js_path], capture_output=True, text=True, timeout=30)
                        os.unlink(js_path)

                        if result.returncode == 0 and os.path.exists('/tmp/quotation_output.docx'):
                            with open('/tmp/quotation_output.docx', 'rb') as f:
                                docx_bytes = f.read()
                            os.unlink('/tmp/quotation_output.docx')
                            st.success("✅ Quotation DOCX ready! Click below to download.")
                            st.download_button(
                                label=f"⬇️ Download {qt_number}.docx",
                                data=docx_bytes,
                                file_name=f"{qt_number}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key="qt_dl_docx"
                            )
                        else:
                            st.error(f"DOCX generation failed. Please use PDF format instead.\n{result.stderr[:300]}")
                    except Exception as e:
                        st.error(f"DOCX generation error: {str(e)}")

st.markdown("---")


# ── CHAT RENDER ───────────────────────────────────────────────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_input := st.chat_input(placeholder=selected_lang['placeholder']):
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.3,
        max_output_tokens=8192,
    )

    api_contents = []
    for msg in st.session_state.messages:
        api_contents.append(
            types.Content(
                role="user" if msg["role"] == "user" else "model",
                parts=[types.Part.from_text(text=msg["content"])]
            )
        )

    try:
        with st.chat_message("model"):
            response_placeholder = st.empty()
            full_response = ""

            response_stream = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=api_contents,
                config=config
            )

            for chunk in response_stream:
                if hasattr(chunk, "text") and chunk.text:
                    full_response += chunk.text
                    response_placeholder.markdown(full_response + "▌")

            if full_response:
                response_placeholder.markdown(full_response)
                st.session_state.messages.append(
                    {"role": "model", "content": full_response}
                )
            else:
                response_placeholder.error("No response received from Gemini.")

    except Exception as e:
        st.error(f"Koneksi API Kendala: {str(e)}")