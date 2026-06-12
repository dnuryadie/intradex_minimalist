import math

# DATABASE MASTER KOMODITAS & KEMASAN EKSPOR
PACKAGING_MASTER = {
    "Cassia Whole": {
        "PP Woven Bag 25 Kg": {"weight": 25.0, "price_per_unit": 7500, "tare_weight": 0.20, "type": "Bag"},
        "PP Woven Bag 50 Kg": {"weight": 50.0, "price_per_unit": 12000, "tare_weight": 0.35, "type": "Bag"}
    },
    "Cassia Powder": {
        "Kraft Paper Bag 20 Kg": {"weight": 20.0, "price_per_unit": 11000, "tare_weight": 0.25, "type": "Bag"},
        "Kraft Paper Bag 25 Kg": {"weight": 25.0, "price_per_unit": 12500, "tare_weight": 0.30, "type": "Bag"}
    },
    "Black Pepper": {
        "PP Woven Bag 25 Kg": {"weight": 25.0, "price_per_unit": 7500, "tare_weight": 0.30, "type": "Bag"}
    },
    "White Pepper": {
        "PP Woven Bag 25 Kg": {"weight": 25.0, "price_per_unit": 7500, "tare_weight": 0.30, "type": "Bag"}
    },
    "Clove": {
        "PP Woven Bag 25 Kg": {"weight": 25.0, "price_per_unit": 7500, "tare_weight": 0.30, "type": "Bag"},
        "PP Woven Bag 50 Kg": {"weight": 50.0, "price_per_unit": 12000, "tare_weight": 0.35, "type": "Bag"}
    },
    "Nutmeg": {
        "PP Woven Bag 25 Kg": {"weight": 25.0, "price_per_unit": 7500, "tare_weight": 0.30, "type": "Bag"},
        "PP Woven Bag 50 Kg": {"weight": 50.0, "price_per_unit": 12000, "tare_weight": 0.35, "type": "Bag"}
    },
    "Vanilla": {
        "Vacuum Bag + Carton 5 Kg": {"weight": 5.0, "price_per_unit": 25000, "tare_weight": 0.50, "type": "Carton"},
        "Vacuum Bag + Carton 10 Kg": {"weight": 10.0, "price_per_unit": 35000, "tare_weight": 0.80, "type": "Carton"}
    },
    "Patchouli Oil": {
        "HDPE Drum 25 Kg": {"weight": 25.0, "price_per_unit": 85000, "tare_weight": 1.80, "type": "Drum"},
        "Steel Drum 180 Kg": {"weight": 180.0, "price_per_unit": 350000, "tare_weight": 18.00, "type": "Drum"}
    }
}

def calculate_packaging_cost(commodity, target_weight_kg, packaging_name, exchange_rate=17500):
    # Pengaman 1: Jika komoditas tidak ada di master data
    if commodity not in PACKAGING_MASTER:
        return {"error": f"Commodity '{commodity}' not found in database."}
        
    # Pengaman 2: Jika nama kemasan tidak ada atau bernilai None
    if not packaging_name or packaging_name not in PACKAGING_MASTER[commodity]:
        return {"error": f"Packaging type '{packaging_name}' not found for {commodity}."}
        
    pack_info = PACKAGING_MASTER[commodity][packaging_name]
    
    # Pengaman 3: Menggunakan .get() dengan nilai default agar kebal terhadap KeyError
    weight_per_unit = pack_info.get("weight", 25)
    price_per_unit = pack_info.get("price_per_unit", 0)
    tare_weight = pack_info.get("tare_weight", 0.0)
    
    # Eksekusi Logika Matematika Pembulatan Karung ke Atas (Ceil)
    total_units_needed = math.ceil(target_weight_kg / weight_per_unit)
    total_packaging_cost_idr = total_units_needed * price_per_unit
    
    # Kalkulasi Estimasi Berat Kotor (Gross Weight) untuk Keperluan Freight
    total_tare_weight = total_units_needed * tare_weight
    gross_weight_estimate = target_weight_kg + total_tare_weight
    
    # Kurs dinamis (dikirim dari app, default 17500 jika tidak ada)
    EXCHANGE_RATE_USD = exchange_rate

    total_packaging_cost_usd = total_packaging_cost_idr / EXCHANGE_RATE_USD
    packaging_cost_per_kg_usd = total_packaging_cost_usd / target_weight_kg
    
    return {
        "commodity": commodity,
        "selected_packaging": packaging_name,
        "packaging_type": pack_info.get("type", "Unit"),
        "weight_per_unit_kg": weight_per_unit,
        "price_per_unit_idr": price_per_unit,
        "total_units_needed": total_units_needed,
        "total_packaging_cost_usd": round(total_packaging_cost_usd, 2),
        "packaging_cost_per_kg_usd": round(packaging_cost_per_kg_usd, 4),
        "net_weight_kg": target_weight_kg,
        "gross_weight_kg": round(gross_weight_estimate, 2),
        "exchange_rate": EXCHANGE_RATE_USD
    }