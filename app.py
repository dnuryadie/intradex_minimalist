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

if len(st.session_state.messages) == 0:
    st.subheader(get_greeting(lang_option))
    st.image("assets/intradex_logo.png", width="stretch")

    tab_pack, tab_fob, tab_pi = st.tabs([
        "📦 Sourcing & Packaging Calculator",
        "🚢 FOB Commercial Calculator",
        "📄 Proforma Invoice Generator"
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

            # ── GENERATE PDF BUTTON ───────────────────────────────────
            st.markdown(" ")
            confirm_msg = CONFIRM_MESSAGES.get(lang_option, CONFIRM_MESSAGES["English"])
            st.info(f"🖨️ **{confirm_msg}**")

            if st.button("📄 Generate & Download Proforma Invoice (PDF)",
                         use_container_width=True, type="primary"):
                if not buyer_name or not buyer_country:
                    st.warning("⚠️ Please fill in at least Buyer Name and Buyer Country.")
                else:
                    issue_date_str = datetime.now().strftime("%d %B %Y")
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

    st.markdown("---")

else:
    st.title("InTradeX-Mate - AI-Powered International Trade Consultant")

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