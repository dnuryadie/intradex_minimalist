import os
import base64
import requests
from datetime import datetime, timedelta
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
from pricing_engine import calculate_packaging_cost, PACKAGING_MASTER
from fob_engine import calculate_fob_price, COMMODITY_FOB_MASTER, DOMESTIC_FREIGHT_COST_IDR
from pi_generator import generate_pi_pdf, CONFIRM_MESSAGES
from pi_docx_generator import generate_pi_docx
from qt_docx_generator import generate_qt_docx

# ── MOBILE-FRIENDLY DOWNLOAD LINK ────────────────────────────────────────────
def mobile_download_link(data, filename: str, mime: str, label: str):
    """Render an <a> tag with a base64 data URI — works on mobile browsers.
    Accepts bytes or any BytesIO-like object."""
    if hasattr(data, "getvalue"):
        raw = data.getvalue()
    elif hasattr(data, "read"):
        data.seek(0)
        raw = data.read()
    else:
        raw = bytes(data)
    b64 = base64.b64encode(raw).decode()
    href = f"data:{mime};base64,{b64}"
    st.markdown(
        f"""
        <a href="{href}" download="{filename}" target="_blank"
           style="display:block;width:100%;text-align:center;padding:10px 0;
                  background:#1B4332;color:#fff;border-radius:8px;
                  font-size:15px;font-weight:600;text-decoration:none;
                  margin-top:6px;">
            {label}
        </a>
        """,
        unsafe_allow_html=True,
    )

# ── 1. CONFIGURATION & INITIALIZATION ────────────────────────────────────────
st.set_page_config(
    page_title="InTradeX-Mate | AI-Powered Trade Consultant",
    page_icon="assets/favicon.png",
    layout="wide"
)

# ── CSS: LOCK SIDEBAR + STYLE CHAT BOX ───────────────────────────────────────
st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            min-width: 333px !important;
            max-width: 333px !important;
        }
        [data-testid="stSidebarResizeHandle"] {
            display: none !important;
        }
        /* Chat box header styling */
        .chat-box-header {
            background: linear-gradient(135deg, #1B4332 0%, #2D6A4F 100%);
            padding: 10px 16px 8px 16px;
            border-radius: 8px 8px 0 0;
            margin-bottom: 0;
        }
        .chat-box-header h4 {
            color: white;
            margin: 0;
            font-size: 15px;
            font-weight: 700;
        }
        .chat-box-header p {
            color: #B7E4C7;
            margin: 2px 0 0 0;
            font-size: 11px;
        }
    </style>
""", unsafe_allow_html=True)

# ── TOP ANCHOR — hero section is always position-zero ────────────────────────
# This invisible div acts as the scroll target so the browser can never land
# below the hero on initial load.
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

# Inject a one-shot JS scroll-reset via an iframe. This fires on every full
# page load (F5 / first visit) but NOT on Streamlit's partial reruns that are
# triggered by widget interaction, so it does not fight the user while they
# type. parent.window is the host page; the iframe itself has height=0.
components.html(
    """
    <script>
        // Only scroll on true page load, not on Streamlit hot-reruns
        if (window.performance && window.performance.navigation.type !== 1) {
            parent.window.scrollTo({ top: 0, behavior: 'instant' });
        } else {
            parent.window.scrollTo({ top: 0, behavior: 'instant' });
        }
    </script>
    """,
    height=0,
    scrolling=False,
)

# ── API KEY ───────────────────────────────────────────────────────────────────
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


# ── HELPER: LOAD KNOWLEDGE BASE (RAG) ────────────────────────────────────────
@st.cache_data(show_spinner=False)
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


# ── 2. SIDEBAR UI & MULTILANGUAGE SELECTOR ─────────────────────────────────
st.sidebar.image("assets/favicon.png", width=150)

st.sidebar.markdown(
    """
    <div style='padding: 2px 0 0 0;'>
        <p style='font-size: 20px; font-weight: 700; margin: 0 0 2px 0; line-height: 1.2;'>InTradeX-Mate</p>
        <p style='font-size: 13px; color: gray; margin: 0 0 1px 0; line-height: 1.4;'>
            A strategic initiative from<br>MAGASTU INDOPRIME GROUP (MIG)
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown("---")

lang_option = st.sidebar.selectbox(
    "🌐 Language",
    ["English", "Bahasa Indonesia"]
)

st.sidebar.markdown("---")

st.sidebar.markdown("🤝 How does **InTradeX-Mate** Supports You?")
st.sidebar.markdown(
    """
    💰 Live Quotation Estimation  
    🚢 Live FOB Pricing & Cost Analysis  
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
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
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
    from datetime import timezone
    wib = timezone(timedelta(hours=7))
    current_hour = datetime.now(wib).hour

    if 5 <= current_hour < 12:
        period = "morning"
    elif 12 <= current_hour < 18:
        period = "afternoon"
    else:
        period = "evening"

    greetings = {
        "English":  {"morning": "👋 Hi, good morning! Welcome to", "afternoon": "👋 Hi, good afternoon! Welcome to", "evening": "👋 Hi, good evening! Welcome to"},
        "Bahasa Indonesia": {"morning": "👋 Hai, selamat pagi. Selamat datang di", "afternoon": "👋 Hai, selamat siang. Selamat datang di", "evening": "👋 Hai, selamat sore. Selamat datang di"},
    }
    return greetings[lang][period]


# ── 5. WELCOME TEXTS ──────────────────────────────────────────────────────────
welcome_texts = {
    "English": {
        "subtitle": "I'm your Trade Intelligence Consultant for Indonesian spices. I can help you with:",
        "bullets": [
            "**Export documents** — Invoice, COA, phytosanitary, B/L",
            "**Incoterms & pricing** — FOB, CIF, DDP calculations",
            "**Import regulations** — Regional compliance (EU, GCC, FDA)"
        ],
        "placeholder": "Ask me anything about Indonesian spices..."
    },
    "Bahasa Indonesia": {
        "subtitle": "Saya adalah Konsultan Perdagangan Internasional untuk rempah-rempah Indonesia. Saya dapat membantu Anda terkait:",
        "bullets": [
            "**Sumber rempah** — Spesifikasi produk, grade, asal usul",
            "**Dokumen ekspor** — Invoice, COA, Karantina/Fitosanitari, B/L",
            "**Incoterms & harga** — Kalkulasi FOB, CIF, DDP",
            "**Regulasi impor** — Kepatuhan regional (EU, GCC, FDA)"
        ],
        "placeholder": "Tanyakan tentang sumber rempah Indonesia, regulasi, harga..."
    },
}

selected_lang = welcome_texts[lang_option]

LANGUAGE_MAP = {
    "English": "English",
    "Bahasa Indonesia": "Indonesian"
}


# ── 6. ENHANCED SYSTEM PROMPT ─────────────────────────────────────────────────
if "current_calc_context" not in st.session_state:
    st.session_state.current_calc_context = "No active calculation on screen."

live_calc_data = st.session_state.current_calc_context

SYSTEM_PROMPT = f"""
You are InTradeX-Mate, an elite AI-powered Trade Intelligence Consultant representing Magastu Indoprime Group (MIG), 
a professional Indonesian spice exporter and trade solutions provider.

IDENTITY & EXPERTISE:
You have deep, authoritative expertise in:
1. Indonesian spices — botanical taxonomy, varieties, grades, cultivation regions, processing, quality standards
2. International trade — Incoterms 2020, export procedures, shipping documentation
3. Export compliance — EU regulations (EFSA, MRLs, coumarin limits), FDA FSMA, GCC requirements
4. FOB/CIF/DDP pricing methodology and cost structures
5. Indonesian export ports and domestic logistics

CRITICAL SPICE KNOWLEDGE (always answer with precision):

CINNAMON DISTINCTION:
- Cassia/Indonesian Cinnamon (Cinnamomum burmannii, C. cassia, C. loureiroi):
  * Thick bark (2-3mm), reddish-brown, bold flavor, HIGH coumarin (1,000–12,200 mg/kg)
  * Indonesia produces Padang/Korintje Cassia (C. burmannii) from West Sumatra
  * Grades: AABB, AA, A — based on uniformity and defects
  * EU Regulation restricts high coumarin foods (Reg. EC 1334/2008)
  * HS Code: 0906.11 (whole), 0906.19 (ground/powder)
- Ceylon/True Cinnamon (Cinnamomum verum, syn. C. zeylanicum):
  * Thin multi-layer quills (<0.5mm), light tan, delicate sweet flavor
  * Very LOW coumarin (<0.04 mg/kg) — EU-safe for daily consumption
  * Premium grade, higher price than cassia
  * Origin: Sri Lanka (primary), India, Madagascar
  * HS Code: 0906.11

NUTMEG DISTINCTION:
- Banda Nutmeg / True Nutmeg (Myristica fragrans):
  * Indonesia produces ~75% of world supply; primary region: Banda Islands, North Maluku
  * Oval-shaped, produces BOTH nutmeg (seed) AND mace (aril covering) commercially
  * Rich, warm, complex aroma; essential oil 5-15%; contains myristicin
  * Grades: ABCD (mixed), SS (premium whole), BWP (broken/lower)
  * HS Code: 0908.11 (whole nutmeg), Mace: 0908.21
- Papuan Nutmeg (Myristica argentea):
  * Origin: Papua / New Guinea region
  * Elongated shape (longer than M. fragrans)
  * Milder aroma, LOWER essential oil, lower market value
  * Does NOT produce commercially valued mace
  * Sometimes used as substitute/adulterant — lower grade
  * HS Code: 0908.19

PEPPER:
- Black Pepper (Piper nigrum): HS 0904.11; Bangka Island, Lampung
- White Pepper (Piper nigrum, ripe & processed): HS 0904.12; Bangka Muntok White Pepper = world premium grade
- Piperine content 5-9% determines pungency

CLOVE (Syzygium aromaticum): HS 0907.10; Maluku, Sulawesi; 70-90% eugenol in oil
VANILLA (Vanilla planifolia): HS 0905.10; Sulawesi, Bali, Papua; Grade A (>25% moisture) premium
PATCHOULI OIL (Pogostemon cablin): HS 3301.29; Indonesia = 85% world supply; Aceh, Sulawesi

CURRENT LIVE CALCULATION DATA:
{live_calc_data}

LANGUAGE RULE:
Always respond ONLY in {LANGUAGE_MAP[lang_option]}.
Never switch language unless explicitly requested by the user.

BUSINESS CONDUCT RULES:
- Provide precise, expert-level answers — never guess or approximate on technical specifications
- When asked about spice varieties, always clarify the exact botanical name and distinguishing characteristics
- Reference specific HS codes, regulations, and compliance requirements accurately
- Use the Knowledge Base information provided when relevant
- Reference live calculation data when the user asks about pricing, packaging, or logistics
- Structure answers clearly with bullet points or tables when appropriate
- If uncertain about a very specific detail, acknowledge it and provide the best available guidance
- Represent MIG professionally as a trusted export partner

KNOWLEDGE BASE:
{knowledge_context}
"""


# ── 7. SESSION STATE INITIALIZATION ──────────────────────────────────────────
if "messages"     not in st.session_state: st.session_state.messages = []
if "fob_result"   not in st.session_state: st.session_state.fob_result = None
if "fob_error"    not in st.session_state: st.session_state.fob_error = None
if "sync_commodity" not in st.session_state: st.session_state.sync_commodity = None
if "sync_volume"    not in st.session_state: st.session_state.sync_volume = None
if "sync_packaging" not in st.session_state: st.session_state.sync_packaging = None
if "reset_counter"  not in st.session_state: st.session_state.reset_counter = 0
if "sync_applied"   not in st.session_state: st.session_state.sync_applied = True
# Tracks whether the user has started typing / sending — used to clear the
# text-area after a successful send without interfering with normal edits.
if "_chat_input_key" not in st.session_state: st.session_state._chat_input_key = 0

live_rate, live_rate_updated, live_rate_ok = fetch_live_usd_idr()


# ── 8. MAIN CONTENT AREA ──────────────────────────────────────────────────────
st.subheader(get_greeting(lang_option))
# Always show the banner/logo (not conditional on message count)
st.image("assets/logo.png", use_container_width=True)

tab_pack, tab_fob, tab_qt, tab_pi = st.tabs([
    "📦 Sourcing & Packaging Calculator",
    "🚢 FOB Commercial Calculator",
    "📄 Quotation Generator",
    "📋 Proforma Invoice Generator"
])


# ── TAB 1: PACKAGING CALCULATOR ──────────────────────────────────────────────
with tab_pack:
    st.markdown("### 📦 Live Sourcing & Packaging Calculator")

    rc = st.session_state.reset_counter

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            pricing_commodity = st.selectbox(
                "Select Commodity", list(PACKAGING_MASTER.keys()),
                index=None, placeholder="-", key=f"pricing_commodity_{rc}"
            )
        with col2:
            pricing_volume = st.number_input(
                "Volume Target (Kg)", min_value=1.0, step=50.0,
                value=None, placeholder="-", key=f"pricing_volume_{rc}"
            )
        with col3:
            if pricing_commodity:
                available_packs = list(PACKAGING_MASTER[pricing_commodity].keys())
                pricing_pack = st.selectbox(
                    "Select Packaging Type", available_packs,
                    index=None, placeholder="-", key=f"pricing_pack_{rc}"
                )
            else:
                st.selectbox("Select Packaging Type", [], disabled=True,
                             placeholder="-", key=f"pricing_pack_disabled_{rc}")
                pricing_pack = None

    if pricing_commodity and pricing_volume and pricing_pack:
        calc_result = calculate_packaging_cost(
            pricing_commodity, pricing_volume, pricing_pack, exchange_rate=live_rate
        )

        if "error" not in calc_result:
            st.markdown("---")
            st.markdown("##### 📦 Logistics & Weight Specifications")
            wc1, wc2, wc3 = st.columns(3)
            with wc1:
                st.metric("Total Units Needed",
                          f"{calc_result['total_units_needed']:,} {calc_result['packaging_type']}(s)")
            with wc2:
                st.metric("Estimated Net Weight", f"{calc_result['net_weight_kg']:,} Kg")
            with wc3:
                st.metric("Estimated Gross Weight", f"{calc_result['gross_weight_kg']:,} Kg",
                          delta=f"+{calc_result['gross_weight_kg'] - calc_result['net_weight_kg']:.2f} Kg Tare")

            st.markdown(" ")
            st.markdown("##### 💵 Commercial Packaging Cost (USD)")
            cc1, cc2 = st.columns(2)
            with cc1:
                st.metric("Total Packaging Cost (USD)", f"$ {calc_result['total_packaging_cost_usd']:,}")
            with cc2:
                st.metric("Packaging Cost/Kg (USD)", f"$ {calc_result['packaging_cost_per_kg_usd']:,}/Kg")

            st.info(
                f"💡 **Formula Breakdown:** \n"
                f"• Unit Price: IDR {calc_result['price_per_unit_idr']:,}/{calc_result['packaging_type']}  \n"
                f"• Total Cost in Local Currency: {calc_result['total_units_needed']:,} units × "
                f"IDR {calc_result['price_per_unit_idr']:,} = "
                f"IDR {calc_result['total_units_needed'] * calc_result['price_per_unit_idr']:,}  \n"
                f"• Exchange Rate: USD 1 = IDR {calc_result['exchange_rate']:,}  \n"
                f"• USD Result: IDR {calc_result['total_units_needed'] * calc_result['price_per_unit_idr']:,} "
                f"÷ IDR {calc_result['exchange_rate']:,} = **USD {calc_result['total_packaging_cost_usd']:,}**"
            )

            st.session_state.current_calc_context = (
                f"User calculated Sourcing {pricing_volume} kg of {pricing_commodity} packed in {pricing_pack}. "
                f"Logistics Specs: Needs {calc_result['total_units_needed']} units. "
                f"Net Weight: {calc_result['net_weight_kg']} Kg, Gross Weight: {calc_result['gross_weight_kg']} Kg. "
                f"Commercial Pricing: Total Cost USD $ {calc_result['total_packaging_cost_usd']:,} "
                f"($ {calc_result['packaging_cost_per_kg_usd']:,}/Kg)."
            )

            COMMODITY_MAP_TO_FOB = {
                "Cassia Whole":  "Cassia Whole",  "Cassia Powder": "Cassia Powder",
                "Black Pepper":  "Black Pepper (Whole)", "White Pepper": "White Pepper (Whole)",
                "Clove":         "Clove",          "Nutmeg":       "Nutmeg",
                "Vanilla":       "Vanilla",         "Patchouli Oil":"Patchouli Oil",
            }
            PACKAGING_MAP_TO_FOB = {
                "PP Woven Bag 25 Kg": "PP Woven Bag 25 Kg", "PP Woven Bag 50 Kg": "PP Woven Bag 50 Kg",
                "Kraft Paper Bag 20 Kg": "Kraft Paper Bag 20 Kg", "Kraft Paper Bag 25 Kg": "Kraft Paper Bag 25 Kg",
                "Vacuum Bag + Carton 5 Kg": "Vacuum Bag + Carton 5 Kg",
                "Vacuum Bag + Carton 10 Kg": "Vacuum Bag + Carton 10 Kg",
                "HDPE Drum 25 Kg": "HDPE Drum 25 Kg", "Steel Drum 180 Kg": "Steel Drum 180 Kg",
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
            st.error(calc_result["error"])
    else:
        st.markdown(
            "<p style='color: #888; font-style: italic; padding-top: 10px;'>"
            "ℹ️ Please select a commodity, target volume, and packaging type to generate the live quotation estimate."
            "</p>", unsafe_allow_html=True
        )
        st.session_state.current_calc_context = "No active calculation on screen."


# ── TAB 2: FOB CALCULATOR ─────────────────────────────────────────────────────
with tab_fob:
    st.subheader("🚢 Live FOB Commercial Calculator")

    synced_commodity = st.session_state.get("sync_commodity")
    synced_volume    = st.session_state.get("sync_volume")
    synced_packaging = st.session_state.get("sync_packaging")

    rc = st.session_state.reset_counter

    fob_commodity_list = list(COMMODITY_FOB_MASTER.keys())
    fob_pack_list = [
        "PP Woven Bag 25 Kg", "PP Woven Bag 50 Kg",
        "Kraft Paper Bag 20 Kg", "Kraft Paper Bag 25 Kg",
        "Vacuum Bag + Carton 5 Kg", "Vacuum Bag + Carton 10 Kg",
        "HDPE Drum 25 Kg", "Steel Drum 180 Kg"
    ]

    if not st.session_state.get("sync_applied", True) and synced_commodity:
        if synced_commodity in fob_commodity_list:
            st.session_state[f"fob_commodity_{rc}"] = synced_commodity
        if synced_volume:
            st.session_state[f"fob_volume_{rc}"] = synced_volume
        if synced_packaging and synced_packaging in fob_pack_list:
            st.session_state[f"fob_packaging_{rc}"] = synced_packaging
        st.session_state.sync_applied = True

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
                "Commodity", fob_commodity_list,
                index=None, placeholder="-", key=f"fob_commodity_{rc}"
            )
            volume_kg = st.number_input(
                "Volume (Kg)", min_value=1.0, value=None,
                placeholder="-", key=f"fob_volume_{rc}"
            )
        with col_f2:
            packaging_type = st.selectbox(
                "Packaging Type", fob_pack_list,
                index=None, placeholder="-", key=f"fob_packaging_{rc}"
            )
            loading_port = st.selectbox(
                "Loading Port", list(DOMESTIC_FREIGHT_COST_IDR.keys()),
                index=None, placeholder="-", key=f"fob_port_{rc}"
            )

        exchange_rate = st.number_input(
            "USD/IDR Exchange Rate", min_value=1, value=live_rate, key=f"fob_exrate_{rc}"
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
        calc_btn  = st.button("⚙️ Calculate FOB", use_container_width=True, type="primary")
    with btn_col2:
        reset_btn = st.button("🔄 Reset", use_container_width=True)

    if reset_btn:
        st.session_state.fob_result = None
        st.session_state.fob_error  = None
        st.session_state.current_calc_context = "No active calculation on screen."
        st.session_state.sync_commodity = None
        st.session_state.sync_volume    = None
        st.session_state.sync_packaging = None
        st.session_state.sync_applied   = True
        st.session_state.reset_counter += 1
        st.rerun()

    if calc_btn:
        if not commodity or not volume_kg or not packaging_type or not loading_port:
            st.warning("⚠️ Please fill in all fields before calculating.")
        else:
            raw_result = calculate_fob_price(
                commodity_name=commodity, volume_kg=volume_kg,
                packaging_type=packaging_type, loading_port=loading_port,
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
                    f"- Margin: {raw_result['margin_percent']}%"
                )

    if st.session_state.get("fob_error"):
        st.error(st.session_state.fob_error)
    elif st.session_state.get("fob_result"):
        result = st.session_state.fob_result
        st.markdown("---")
        st.markdown("### 📊 FOB Pricing")

        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c1: st.metric("FOB Price / Kg (USD)", f"${result['fob_price_per_kg']:.4f}")
        with r1c2: st.metric("FOB Total Value (USD)", f"${result['fob_total_usd']:,.2f}")
        with r1c3: st.metric("Total Cost (USD)", f"${result['total_cost_usd']:,.2f}")

        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1: st.metric("Profit (USD)", f"${result['profit_usd']:,.2f}")
        with r2c2: st.metric("Margin", f"{result['margin_percent']}%")
        with r2c3: st.metric("Exchange Rate", f"IDR {result['exchange_rate']:,}")

        st.success(
            f"**FOB Calculation Validation**\n\n"
            f"Total Cost &nbsp;&nbsp;&nbsp;&nbsp; **USD {result['total_cost_usd']:,.2f}**\n\n"
            f"Margin &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; **{result['margin_percent']}%**\n\n"
            f"Profit &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; **USD {result['profit_usd']:,.2f}**\n\n"
            f"✅ &nbsp;FOB calculation completed successfully."
        )

        st.markdown("### 🚢 Shipment Information")
        st.write(f"**Commodity:** {result['commodity']}")
        st.write(f"**HS Code:** {result['hs_code']}")
        st.write(f"**Origin:** {result['origin']}")
        st.write(f"**Loading Port:** {result['loading_port']}")
        st.write(f"**Net Weight:** {result['net_weight_kg']:,} Kg")
        st.write(f"**Gross Weight:** {result['gross_weight_kg']:,} Kg")
        st.write(f"**Total Packaging Units:** {result['total_units_needed']:,}")

        st.markdown("### 🔍 Cost Breakdown (IDR & USD)")
        breakdown = result["breakdown_total"]
        er = result.get("exchange_rate", 17500)
        import pandas as pd
        breakdown_rows = []
        for key, idr_val in breakdown.items():
            label = key.replace("_idr", "").replace("_", " ").title()
            usd_val = idr_val / er
            pct = (idr_val / sum(breakdown.values()) * 100) if sum(breakdown.values()) > 0 else 0
            breakdown_rows.append({
                "Cost Component": label, "IDR": f"Rp {idr_val:,.0f}",
                "USD": f"${usd_val:,.2f}", "Share (%)": f"{pct:.1f}%"
            })
        st.dataframe(pd.DataFrame(breakdown_rows), use_container_width=True, hide_index=True)


# ── TAB 3: PROFORMA INVOICE GENERATOR ────────────────────────────────────────
with tab_pi:
    st.subheader("📄 Live Proforma Invoice Generator")
    fob_data = st.session_state.get("fob_result")

    if not fob_data:
        st.info(
            "ℹ️ No active FOB calculation found. "
            "Please complete a FOB calculation in the **🚢 FOB Commercial Calculator** tab first."
        )
    else:
        st.success(
            f"✅ FOB data loaded: **{fob_data['commodity']}** — "
            f"{fob_data['volume_kg']:,} Kg @ USD {fob_data['fob_price_per_kg']:.4f}/Kg "
            f"| Total: **USD {fob_data['fob_total_usd']:,.2f}**"
        )
        st.markdown("---")

        COUNTRY_LIST = [
            "Afghanistan","Albania","Algeria","Andorra","Angola","Antigua and Barbuda",
            "Argentina","Armenia","Australia","Austria","Azerbaijan","Bahamas","Bahrain",
            "Bangladesh","Barbados","Belarus","Belgium","Belize","Benin","Bhutan",
            "Bolivia","Bosnia and Herzegovina","Botswana","Brazil","Brunei","Bulgaria",
            "Burkina Faso","Burundi","Cabo Verde","Cambodia","Cameroon","Canada",
            "Central African Republic","Chad","Chile","China","Colombia","Comoros",
            "Congo (Brazzaville)","Congo (Kinshasa)","Costa Rica","Croatia","Cuba",
            "Cyprus","Czech Republic","Denmark","Djibouti","Dominica","Dominican Republic",
            "Ecuador","Egypt","El Salvador","Equatorial Guinea","Eritrea","Estonia",
            "Eswatini","Ethiopia","Fiji","Finland","France","Gabon","Gambia","Georgia",
            "Germany","Ghana","Greece","Grenada","Guatemala","Guinea","Guinea-Bissau",
            "Guyana","Haiti","Honduras","Hungary","Iceland","India","Indonesia","Iran",
            "Iraq","Ireland","Israel","Italy","Jamaica","Japan","Jordan","Kazakhstan",
            "Kenya","Kiribati","Kuwait","Kyrgyzstan","Laos","Latvia","Lebanon","Lesotho",
            "Liberia","Libya","Liechtenstein","Lithuania","Luxembourg","Madagascar",
            "Malawi","Malaysia","Maldives","Mali","Malta","Marshall Islands","Mauritania",
            "Mauritius","Mexico","Micronesia","Moldova","Monaco","Mongolia","Montenegro",
            "Morocco","Mozambique","Myanmar","Namibia","Nauru","Nepal","Netherlands",
            "New Zealand","Nicaragua","Niger","Nigeria","North Korea","North Macedonia",
            "Norway","Oman","Pakistan","Palau","Palestine","Panama","Papua New Guinea",
            "Paraguay","Peru","Philippines","Poland","Portugal","Qatar","Romania","Russia",
            "Rwanda","Saint Kitts and Nevis","Saint Lucia","Saint Vincent and the Grenadines",
            "Samoa","San Marino","Sao Tome and Principe","Saudi Arabia","Senegal","Serbia",
            "Seychelles","Sierra Leone","Singapore","Slovakia","Slovenia","Solomon Islands",
            "Somalia","South Africa","South Korea","South Sudan","Spain","Sri Lanka",
            "Sudan","Suriname","Sweden","Switzerland","Syria","Taiwan","Tajikistan",
            "Tanzania","Thailand","Timor-Leste","Togo","Tonga","Trinidad and Tobago",
            "Tunisia","Turkey","Turkmenistan","Tuvalu","Uganda","Ukraine",
            "United Arab Emirates","United Kingdom","United States","Uruguay","Uzbekistan",
            "Vanuatu","Vatican City","Venezuela","Vietnam","Yemen","Zambia","Zimbabwe"
        ]

        st.markdown("#### 🏢 Seller & Buyer Information")
        pi_col1, pi_col2 = st.columns(2)
        with pi_col1:
            st.markdown("**Seller**")
            seller_name    = st.text_input("Seller Name",    placeholder="e.g. Magastu Indoprime Group (MIG)")
            seller_address = st.text_input("Seller Address", placeholder="e.g. East Seram, Maluku, Indonesia")
            seller_country = st.selectbox("Seller Country", COUNTRY_LIST,
                                          index=COUNTRY_LIST.index("Indonesia"), key="seller_country_select")
            seller_email   = st.text_input("Seller Email",  placeholder="e.g. trade@magastu.com")
            seller_phone   = st.text_input("Seller Phone",  placeholder="e.g. +62 21 XXXX XXXX")
        with pi_col2:
            st.markdown("**Buyer / Consignee**")
            buyer_name    = st.text_input("Buyer Name",    placeholder="e.g. Spice Trading GmbH")
            buyer_address = st.text_input("Buyer Address", placeholder="Full address")
            buyer_country = st.selectbox("Buyer Country", COUNTRY_LIST, index=None,
                                         placeholder="- Select country -", key="buyer_country_select")
            buyer_email   = st.text_input("Buyer Email",  placeholder="e.g. import@spicetrading.de")
            buyer_phone   = st.text_input("Buyer Phone",  placeholder="e.g. +49 40 XXXX XXXX")

        st.markdown("#### 📋 Commercial Terms")
        t1, t2, t3 = st.columns(3)
        with t1:
            payment_terms = st.selectbox("Payment Terms", [
                "100% T/T in Advance", "50% T/T Advance, 50% Before Shipment",
                "30% T/T Advance, 70% Against B/L Copy", "Letter of Credit (L/C) at Sight",
                "Letter of Credit (L/C) 30 Days", "Letter of Credit (L/C) 60 Days",
                "Documents Against Payment (D/P)"
            ])
        with t2:
            validity_days = st.number_input("Price Validity (Days)", min_value=1, max_value=90, value=14)
        with t3:
            pi_number = st.text_input("PI Number",
                                      value=f"InTradeX-Mate/PI/{datetime.now().strftime('%d%b%Y').upper()}/000001")

        st.markdown("#### 🏦 Bank Details & Notes")
        bc, nc = st.columns(2)
        with bc:
            bank_details = st.text_area("Bank Details",
                placeholder="Bank Name:\nAccount Name:\nAccount Number:\nSwift / BIC Code:\nBank Address:",
                height=130)
        with nc:
            custom_notes = st.text_area("Additional Notes (optional — leave blank for default)",
                placeholder="e.g. special handling instructions, certifications required...", height=130)

        ctx = st.session_state.get("current_calc_context", "")
        packaging_from_ctx = (
            ctx.split("Packaging: ")[1].split("\n")[0].split(" —")[0].strip()
            if "Packaging:" in ctx else "As per FOB calculation"
        )

        st.markdown("---")

        if buyer_name:
            st.markdown("#### 👁️ Proforma Invoice Preview")
            issue_date_prev = datetime.now().strftime("%d %B %Y")
            valid_prev = (datetime.now() + timedelta(days=int(validity_days))).strftime("%d %B %Y")
            with st.container(border=True):
                import pandas as _pd
                st.markdown(f"**PI:** `{pi_number}` &nbsp;&nbsp; **Issue:** {issue_date_prev} &nbsp;&nbsp; **Valid Until:** {valid_prev} ({validity_days} days)")
                st.markdown("---")
                pp1, pp2 = st.columns(2)
                with pp1:
                    st.markdown("**SELLER**")
                    st.markdown(f"{seller_name or '—'}  \n{seller_address or '—'}  \n{seller_country}  \n{seller_email or '—'}  \n{seller_phone or '—'}")
                with pp2:
                    st.markdown("**BUYER / CONSIGNEE**")
                    st.markdown(f"{buyer_name or '—'}  \n{buyer_address or '—'}  \n{buyer_country or '—'}  \n{buyer_email or '—'}  \n{buyer_phone or '—'}")
                st.markdown("---")
                st.markdown("**COMMODITY & PRICING**")
                _df_prev = _pd.DataFrame([{
                    "Commodity": fob_data['commodity'], "HS Code": fob_data['hs_code'],
                    "Qty (Kg)": f"{fob_data['volume_kg']:,}",
                    "Unit Price (USD/Kg)": f"${fob_data['fob_price_per_kg']:.4f}",
                    "Total FOB (USD)": f"${fob_data['fob_total_usd']:,.2f}",
                    "Incoterm": f"FOB {fob_data['loading_port']}"
                }])
                st.dataframe(_df_prev, use_container_width=True, hide_index=True)
                st.markdown(f"**Payment Terms:** {payment_terms}")

        st.markdown("#### 📥 Download Format")
        pi_format = st.radio("Select output format:", ["PDF", "DOCX (Word)"],
                             horizontal=True, key="pi_format_radio")

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
                        try:
                            pdf_buf = generate_pi_pdf(
                                pi_number=pi_number, issue_date_str=issue_date_str,
                                validity_days=validity_days, seller_name=seller_name,
                                seller_address=seller_address, seller_country=seller_country,
                                seller_email=seller_email, seller_phone=seller_phone,
                                buyer_name=buyer_name, buyer_address=buyer_address,
                                buyer_country=buyer_country, buyer_email=buyer_email,
                                buyer_phone=buyer_phone, fob_data=fob_data,
                                packaging_type=packaging_from_ctx, payment_terms=payment_terms,
                                bank_details=bank_details, notes=custom_notes, lang=lang_option
                            )
                            st.success("✅ PDF ready! Tap the link below to download.")
                            mobile_download_link(
                                data=pdf_buf,
                                filename=f"{pi_number}.pdf",
                                mime="application/pdf",
                                label=f"⬇️ Download {pi_number}.pdf"
                            )
                        except Exception as e:
                            st.error(f"PDF generation error: {str(e)}")

                else:  # DOCX — Python python-docx (no Node.js required)
                    with st.spinner("Generating DOCX..."):
                        try:
                            docx_buf = generate_pi_docx(
                                pi_number=pi_number, issue_date_str=issue_date_str,
                                validity_days=validity_days, seller_name=seller_name,
                                seller_address=seller_address, seller_country=seller_country,
                                seller_email=seller_email, seller_phone=seller_phone,
                                buyer_name=buyer_name, buyer_address=buyer_address,
                                buyer_country=buyer_country, buyer_email=buyer_email,
                                buyer_phone=buyer_phone, fob_data=fob_data,
                                packaging_type=packaging_from_ctx, payment_terms=payment_terms,
                                bank_details=bank_details, notes=custom_notes, lang=lang_option
                            )
                            st.success("✅ DOCX ready! Tap the link below to download.")
                            mobile_download_link(
                                data=docx_buf,
                                filename=f"{pi_number}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                label=f"⬇️ Download {pi_number}.docx"
                            )
                        except Exception as e:
                            st.error(f"DOCX generation error: {str(e)}")


# ── TAB 4: QUOTATION GENERATOR ────────────────────────────────────────────────
with tab_qt:
    st.subheader("📋 Live FOB Quotation Generator")
    fob_data_qt = st.session_state.get("fob_result")

    if not fob_data_qt:
        st.info(
            "ℹ️ No active FOB calculation found. "
            "Please complete a FOB calculation in the **🚢 FOB Commercial Calculator** tab first."
        )
    else:
        st.success(
            f"✅ FOB data loaded: **{fob_data_qt['commodity']}** — "
            f"{fob_data_qt['volume_kg']:,} Kg @ USD {fob_data_qt['fob_price_per_kg']:.4f}/Kg "
            f"| Total: **USD {fob_data_qt['fob_total_usd']:,.2f}**"
        )
        st.markdown("---")

        st.markdown("#### 🏢 Quotation Parties")
        qt_col1, qt_col2 = st.columns(2)
        with qt_col1:
            qt_seller_name    = st.text_input("Your Company Name", placeholder="e.g. Magastu Indoprime Group (MIG)", key="qt_seller_name")
            qt_seller_address = st.text_input("Your Address",      placeholder="e.g. Jakarta, Indonesia", key="qt_seller_addr")
            qt_seller_email   = st.text_input("Your Email",        placeholder="e.g. trade@magastu.com", key="qt_seller_email")
            qt_seller_phone   = st.text_input("Your Phone / WhatsApp", placeholder="e.g. +62 812 XXXX XXXX", key="qt_seller_phone")
        with qt_col2:
            qt_buyer_name    = st.text_input("Buyer / Recipient Name", placeholder="e.g. Spice Trading GmbH", key="qt_buyer_name")
            qt_buyer_company = st.text_input("Buyer Company",          placeholder="e.g. GmbH, Pty. Ltd., Inc.", key="qt_buyer_company")
            qt_buyer_email   = st.text_input("Buyer Email",            placeholder="e.g. import@spicetrading.de", key="qt_buyer_email")
            qt_buyer_country = st.selectbox("Buyer Country", COUNTRY_LIST, index=None, placeholder="- Select Country -", key="qt_buyer_country")

        st.markdown("#### 📋 Quotation Terms")
        qt_t1, qt_t2, qt_t3 = st.columns(3)
        with qt_t1:
            qt_payment = st.selectbox("Payment Terms", [
                "100% T/T in Advance", "50% T/T Advance, 50% Before Shipment",
                "30% T/T Advance, 70% Against B/L Copy",
                "Letter of Credit (L/C) at Sight", "Documents Against Payment (D/P)"
            ], key="qt_payment")
        with qt_t2:
            qt_validity = st.number_input("Price Validity (Days)", min_value=1, max_value=90, value=14, key="qt_validity")
        with qt_t3:
            qt_number = st.text_input("Quotation Number",
                value=f"InTradeX-Mate/QT/{datetime.now().strftime('%d%b%Y').upper()}/000001", key="qt_number")

        qt_notes = st.text_area("Additional Notes (optional)",
            placeholder="e.g. Minimum order quantity, lead time, certification details...",
            height=100, key="qt_notes")

        st.markdown("---")

        if qt_buyer_name:
            st.markdown("#### 👁️ Quotation Preview")
            issue_date_qt   = datetime.now().strftime("%d %B %Y")
            valid_until_qt  = (datetime.now() + timedelta(days=int(qt_validity))).strftime("%d %B %Y")

            with st.container(border=True):
                st.markdown(f"**QUOTATION** &nbsp;&nbsp; `{qt_number}`")
                st.markdown(f"**Issue Date:** {issue_date_qt} &nbsp;&nbsp; **Valid Until:** {valid_until_qt} ({qt_validity} days)")
                st.markdown("---")
                qp1, qp2 = st.columns(2)
                with qp1:
                    st.markdown("**FROM (Seller)**")
                    st.markdown(f"{qt_seller_name or '—'}\n{qt_seller_address or '—'}\n{qt_seller_email or '—'} | {qt_seller_phone or '—'}")
                with qp2:
                    st.markdown("**TO (Buyer)**")
                    st.markdown(f"{qt_buyer_name or '—'} — {qt_buyer_company or '—'}\n{qt_buyer_country or '—'}\n{qt_buyer_email or '—'}")
                st.markdown("---")
                st.markdown("**COMMODITY & PRICING**")
                import pandas as pd
                qt_preview_df = pd.DataFrame([{
                    "Commodity": fob_data_qt['commodity'], "HS Code": fob_data_qt['hs_code'],
                    "Origin": fob_data_qt['origin'], "Volume (Kg)": f"{fob_data_qt['volume_kg']:,}",
                    "Unit Price (USD/Kg)": f"${fob_data_qt['fob_price_per_kg']:.4f}",
                    "Total FOB Value (USD)": f"${fob_data_qt['fob_total_usd']:,.2f}",
                    "Incoterm": f"FOB {fob_data_qt['loading_port']}"
                }])
                st.dataframe(qt_preview_df, use_container_width=True, hide_index=True)
                st.markdown(f"**Payment Terms:** {qt_payment}")
                if qt_notes:
                    st.markdown(f"**Notes:** {qt_notes}")

        st.markdown("#### 📥 Download Quotation")
        qt_format = st.radio("Select output format:", ["PDF", "DOCX (Word)"],
                             horizontal=True, key="qt_format")

        st.info("🖨️ Review the preview above, then click Generate to download your Quotation.")

        if st.button("📄 Generate & Download Quotation",
                     use_container_width=True, type="primary", key="qt_generate_btn"):
            if not qt_buyer_name:
                st.warning("⚠️ Please fill in at least the Buyer Name.")
            else:
                issue_date_qt_gen  = datetime.now().strftime("%d %B %Y")
                valid_until_qt_gen = (datetime.now() + timedelta(days=int(qt_validity))).strftime("%d %B %Y")

                if qt_format == "PDF":
                    try:
                        from reportlab.lib.pagesizes import A4
                        from reportlab.lib import colors as rl_colors
                        from reportlab.lib.units import cm
                        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                                        Paragraph, Spacer, HRFlowable)
                        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
                        import io

                        buf = io.BytesIO()
                        doc = SimpleDocTemplate(
                            buf, pagesize=A4,
                            leftMargin=1.8*cm, rightMargin=1.8*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm
                        )

                        DARK_GREEN  = rl_colors.HexColor("#1B5E20")
                        MID_GREEN   = rl_colors.HexColor("#2E7D32")
                        LIGHT_GREEN = rl_colors.HexColor("#E8F5E9")
                        GRAY_TEXT   = rl_colors.HexColor("#555555")
                        WHITE       = rl_colors.white

                        # ── FIX: added leading & wordWrap to prevent subtitle truncation ──
                        title_style = ParagraphStyle("Title", fontSize=20, fontName="Helvetica-Bold",
                                                     textColor=WHITE, alignment=TA_CENTER,
                                                     spaceAfter=2, leading=26)
                        sub_style   = ParagraphStyle("Sub", fontSize=8, fontName="Helvetica",
                                                     textColor=WHITE, alignment=TA_CENTER,
                                                     leading=11, wordWrap="CJK")
                        body_style  = ParagraphStyle("Body", fontSize=9, fontName="Helvetica",
                                                     textColor=rl_colors.black, leading=13)
                        label_style = ParagraphStyle("Label", fontSize=8, fontName="Helvetica-Bold",
                                                     textColor=GRAY_TEXT)
                        small_style = ParagraphStyle("Small", fontSize=8, fontName="Helvetica",
                                                     textColor=GRAY_TEXT)

                        story = []
                        page_w = A4[0] - 3.6*cm

                        # ── HEADER ──
                        header_tbl = Table([[Paragraph("QUOTATION", title_style)]], colWidths=[page_w])
                        header_tbl.setStyle(TableStyle([
                            ("BACKGROUND", (0,0), (-1,-1), DARK_GREEN),
                            ("TOPPADDING", (0,0), (-1,-1), 12),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                        ]))
                        story.append(header_tbl)

                        # ── FIX: subtitle with full width, adequate padding ──
                        sub_tbl = Table([[Paragraph(
                            "InTradeX-Mate  \u2502  A Strategic Initiative from MAGASTU INDOPRIME GROUP (MIG)  \u2502  Indonesian Spice Export",
                            sub_style
                        )]], colWidths=[page_w])
                        sub_tbl.setStyle(TableStyle([
                            ("BACKGROUND", (0,0), (-1,-1), MID_GREEN),
                            ("TOPPADDING", (0,0), (-1,-1), 5),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
                            ("LEFTPADDING", (0,0), (-1,-1), 10),
                            ("RIGHTPADDING", (0,0), (-1,-1), 10),
                        ]))
                        story.append(sub_tbl)
                        story.append(Spacer(1, 0.3*cm))

                        # ── QT NUMBER / DATE / VALIDITY ──
                        meta_data = [
                            ["QT Number", qt_number, "Issue Date", issue_date_qt_gen],
                            ["Valid Until", f"{valid_until_qt_gen} ({qt_validity} days)", "", ""]
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
                            Paragraph("Company Name", label_style), Paragraph(qt_seller_name or "—", body_style),
                            Paragraph("Address", label_style), Paragraph(qt_seller_address or "—", body_style),
                            Paragraph("Country", label_style), Paragraph("Indonesia", body_style),
                            Paragraph("Email", label_style), Paragraph(qt_seller_email or "—", body_style),
                            Paragraph("Phone / WhatsApp", label_style), Paragraph(qt_seller_phone or "—", body_style),
                        ]
                        buyer_block = [
                            Paragraph("BUYER / RECIPIENT", ParagraphStyle("BH", fontSize=9, fontName="Helvetica-Bold",
                                                                           textColor=WHITE, backColor=DARK_GREEN,
                                                                           leftIndent=4, rightIndent=4, spaceAfter=4)),
                            Paragraph("Company Name", label_style),
                            Paragraph(f"{qt_buyer_name or '—'} {qt_buyer_company or ''}", body_style),
                            Paragraph("Country", label_style), Paragraph(qt_buyer_country or "—", body_style),
                            Paragraph("Email", label_style), Paragraph(qt_buyer_email or "—", body_style),
                        ]

                        party_tbl = Table([[seller_block, buyer_block]], colWidths=[half, half])
                        party_tbl.setStyle(TableStyle([
                            ("VALIGN", (0,0), (-1,-1), "TOP"),
                            ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
                            ("BOX", (0,0), (0,0), 0.5, rl_colors.HexColor("#CCCCCC")),
                            ("BOX", (1,0), (1,0), 0.5, rl_colors.HexColor("#CCCCCC")),
                        ]))
                        story.append(party_tbl)
                        story.append(Spacer(1, 0.3*cm))

                        # ── COMMODITY & PRICING TABLE ──
                        sec_hdr = Table([[Paragraph("COMMODITY & PRICING DETAILS",
                            ParagraphStyle("SecH", fontSize=9, fontName="Helvetica-Bold",
                                          textColor=WHITE))]], colWidths=[page_w])
                        sec_hdr.setStyle(TableStyle([
                            ("BACKGROUND", (0,0), (-1,-1), DARK_GREEN),
                            ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                            ("LEFTPADDING", (0,0), (-1,-1), 6),
                        ]))
                        story.append(sec_hdr)

                        col_w = [page_w*0.35, page_w*0.13, page_w*0.13, page_w*0.17, page_w*0.22]
                        price_hdr_row = ["Description", "HS Code", "Qty (Kg)", "Unit Price\n(USD/Kg)", "Total (USD)"]
                        price_data_row = [
                            fob_data_qt['commodity'], fob_data_qt['hs_code'],
                            f"{fob_data_qt['volume_kg']:,}", f"${fob_data_qt['fob_price_per_kg']:.4f}",
                            f"${fob_data_qt['fob_total_usd']:,.2f}"
                        ]
                        total_row_qt = ["", "", "", "TOTAL FOB VALUE", f"${fob_data_qt['fob_total_usd']:,.2f}"]
                        price_tbl = Table([price_hdr_row, price_data_row, total_row_qt], colWidths=col_w)
                        price_tbl.setStyle(TableStyle([
                            ("BACKGROUND", (0,0), (-1,0), LIGHT_GREEN),
                            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                            ("FONTSIZE", (0,0), (-1,-1), 9),
                            ("FONTNAME", (3,2), (-1,2), "Helvetica-Bold"),
                            ("TEXTCOLOR", (3,2), (-1,2), DARK_GREEN),
                            ("ALIGN", (2,0), (-1,-1), "RIGHT"),
                            ("GRID", (0,0), (-1,1), 0.5, rl_colors.HexColor("#CCCCCC")),
                            ("BOX", (0,0), (-1,-1), 0.5, rl_colors.HexColor("#CCCCCC")),
                            ("TOPPADDING", (0,0), (-1,-1), 4),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                            ("LEFTPADDING", (0,0), (-1,-1), 5),
                        ]))
                        story.append(price_tbl)
                        story.append(Spacer(1, 0.3*cm))

                        # ── SHIPMENT DETAILS ──
                        ship_data = [
                            ["Incoterm", f"FOB {fob_data_qt['loading_port']}", "Origin", fob_data_qt['origin']],
                            ["Net Weight", f"{fob_data_qt['volume_kg']:,} Kg",
                             "Gross Weight", f"{fob_data_qt.get('gross_weight_kg', '—')} Kg"],
                            ["Payment Terms", qt_payment, "Price Validity",
                             f"{valid_until_qt_gen} ({qt_validity} days)"],
                        ]
                        ship_tbl = Table(ship_data, colWidths=[3*cm, 8*cm, 2.5*cm, 4.5*cm])
                        ship_tbl.setStyle(TableStyle([
                            ("FONTNAME", (0,0), (-1,-1), "Helvetica"), ("FONTSIZE", (0,0), (-1,-1), 9),
                            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"), ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
                            ("TEXTCOLOR", (0,0), (0,-1), DARK_GREEN), ("TEXTCOLOR", (2,0), (2,-1), DARK_GREEN),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                            ("GRID", (0,0), (-1,-1), 0.5, rl_colors.HexColor("#EEEEEE")),
                        ]))
                        story.append(ship_tbl)

                        if qt_notes:
                            story.append(Spacer(1, 0.2*cm))
                            story.append(HRFlowable(width="100%", thickness=0.5, color=rl_colors.HexColor("#CCCCCC")))
                            story.append(Spacer(1, 0.1*cm))
                            story.append(Paragraph("Notes & Conditions",
                                ParagraphStyle("NH", fontSize=9, fontName="Helvetica-Bold", textColor=DARK_GREEN)))
                            story.append(Paragraph(qt_notes, body_style))

                        story.append(Spacer(1, 0.5*cm))
                        story.append(HRFlowable(width="100%", thickness=0.5, color=DARK_GREEN))
                        story.append(Spacer(1, 0.1*cm))
                        story.append(Paragraph(
                            f"Generated by InTradeX-Mate  |  {qt_number}  |  Issued: {issue_date_qt_gen}",
                            ParagraphStyle("Footer", fontSize=7, fontName="Helvetica",
                                           textColor=GRAY_TEXT, alignment=TA_CENTER)
                        ))

                        doc.build(story)
                        buf.seek(0)

                        st.success("✅ Quotation PDF ready! Tap the link below to download.")
                        mobile_download_link(
                            data=buf,
                            filename=f"{qt_number}.pdf",
                            mime="application/pdf",
                            label=f"⬇️ Download {qt_number}.pdf"
                        )
                    except Exception as e:
                        st.error(f"PDF generation error: {str(e)}")

                else:  # DOCX — Python python-docx (no Node.js required)
                    try:
                        issue_date_qt_gen  = datetime.now().strftime("%d %B %Y")
                        valid_until_qt_gen = (datetime.now() + timedelta(days=int(qt_validity))).strftime("%d %B %Y")

                        with st.spinner("Generating DOCX..."):
                            docx_buf = generate_qt_docx(
                                qt_number=qt_number,
                                issue_date_str=issue_date_qt_gen,
                                valid_until_str=valid_until_qt_gen,
                                qt_validity=qt_validity,
                                qt_seller_name=qt_seller_name,
                                qt_seller_address=qt_seller_address,
                                qt_seller_email=qt_seller_email,
                                qt_seller_phone=qt_seller_phone,
                                qt_buyer_name=qt_buyer_name,
                                qt_buyer_company=qt_buyer_company,
                                qt_buyer_email=qt_buyer_email,
                                qt_buyer_country=qt_buyer_country,
                                fob_data=fob_data_qt,
                                qt_payment=qt_payment,
                                qt_notes=qt_notes
                            )
                        st.success("✅ Quotation DOCX ready! Tap the link below to download.")
                        mobile_download_link(
                            data=docx_buf,
                            filename=f"{qt_number}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            label=f"⬇️ Download {qt_number}.docx"
                        )
                    except Exception as e:
                        st.error(f"DOCX generation error: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# AI EXPORT CONSULTANT SECTION — positioned BELOW all primary business tools
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")

# ── Section anchor (so sidebar link can jump here, but load never lands here) ─
st.markdown('<a id="ai-consultant"></a>', unsafe_allow_html=True)

# ── Chatbot header ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="chat-box-header">
    <h4>🤖 InTradeX-Mate | AI Export Consultant</h4>
    <p>Your intelligence partner for Indonesian spices &amp; global trade</p>
</div>
""", unsafe_allow_html=True)

# ── Welcome message inside the container when no messages ─────────────────────
if len(st.session_state.messages) == 0:
    with st.container(border=True):
        st.markdown(f"**{selected_lang['subtitle']}**")
        for bullet in selected_lang["bullets"]:
            st.markdown(f"- {bullet}")
        st.markdown(" ")
        st.caption("💡 You can also ask about the current calculation shown above.")

# ── Scrollable fixed-height message container ─────────────────────────────────
with st.container(height=150, border=True):
    if st.session_state.messages:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    else:
        st.markdown(
            "<div style='color: #aaa; text-align: center; padding-top: 180px; font-size: 13px;'>"
            "💬 Your conversation will appear here…"
            "</div>",
            unsafe_allow_html=True
        )

# ── Chat input: text_area + button — does NOT grab focus or scroll the page ───
# st.chat_input() is intentionally avoided here because it auto-focuses on
# every render, which causes the browser to jump away from the hero banner on
# page load. st.text_area is a passive widget with no auto-focus behaviour.
st.markdown(
    "<p style='margin: 8px 0 4px 0; font-size: 14px; color: #555;'>💬 Ask the Consultant:</p>",
    unsafe_allow_html=True
)
_ck = st.session_state._chat_input_key          # key rotates after each send
_chat_cols = st.columns([5, 1])
with _chat_cols[0]:
    user_input = st.text_area(
        label="chat_message",
        label_visibility="collapsed",
        placeholder=selected_lang["placeholder"],
        height=80,
        key=f"chat_textarea_{_ck}",
    )
with _chat_cols[1]:
    # Vertical spacer so button aligns with the bottom of the text area
    st.markdown("<div style='padding-top: 27px;'></div>", unsafe_allow_html=True)
    send_clicked = st.button(
        "Send ➤",
        use_container_width=True,
        type="primary",
        key=f"chat_send_{_ck}",
    )

if send_clicked and user_input and user_input.strip():
    st.session_state.messages.append({"role": "user", "content": user_input.strip()})

    # Rebuild system prompt with latest calc context
    live_calc_data = st.session_state.current_calc_context
    system_prompt_live = SYSTEM_PROMPT.replace(
        f"CURRENT LIVE CALCULATION DATA:\n{st.session_state.current_calc_context}",
        f"CURRENT LIVE CALCULATION DATA:\n{live_calc_data}"
    )

    config = types.GenerateContentConfig(
        system_instruction=system_prompt_live,
        temperature=0.25,
        max_output_tokens=8192,
    )

    api_contents = [
        types.Content(
            role="user" if msg["role"] == "user" else "model",
            parts=[types.Part.from_text(text=msg["content"])]
        )
        for msg in st.session_state.messages
    ]

    try:
        response_stream = client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=api_contents,
            config=config
        )

        full_response = ""
        for chunk in response_stream:
            if hasattr(chunk, "text") and chunk.text:
                full_response += chunk.text

        if full_response:
            st.session_state.messages.append({"role": "model", "content": full_response})
        else:
            st.session_state.messages.append({
                "role": "model",
                "content": "I apologize — I received an empty response. Please try rephrasing your question."
            })
    except Exception as e:
        err_msg = str(e)
        if "quota" in err_msg.lower() or "429" in err_msg:
            friendly = "⚠️ API quota limit reached. Please wait a moment and try again."
        elif "blocked" in err_msg.lower() or "safety" in err_msg.lower():
            friendly = "⚠️ The response was blocked by safety filters. Please rephrase your question."
        elif "timeout" in err_msg.lower() or "deadline" in err_msg.lower():
            friendly = "⚠️ Request timed out. Please try again."
        else:
            friendly = f"⚠️ Unable to generate response: {err_msg}"
        st.session_state.messages.append({"role": "model", "content": friendly})

    # Rotate the key so the text_area clears after send, then rerun
    st.session_state._chat_input_key += 1
    st.rerun()

