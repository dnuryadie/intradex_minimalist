import math

# ==============================================================================
# MASTER DATA KOMODITAS FOB EXPORT (Cost per KG dalam IDR)
# ==============================================================================
COMMODITY_FOB_MASTER = {
    "Black Pepper (Whole)": {
        "hs_code": "0904.11",
        "origin": "Lampung, Indonesia",
        "raw_material_idr": 65000,
        "processing_idr": 8000,
        "packaging_idr": 2500,
        "documentation_idr": 3500,
        "port_handling_idr": 2000,
        "margin_percent": 20
    },
    "White Pepper (Whole)": {
        "hs_code": "0904.12",
        "origin": "Bangka Belitung, Indonesia",
        "raw_material_idr": 85000,
        "processing_idr": 10000,
        "packaging_idr": 2500,
        "documentation_idr": 3500,
        "port_handling_idr": 2000,
        "margin_percent": 20
    },
    "Cassia Whole": {
        "hs_code": "0906.11",
        "origin": "Kerinci, Indonesia",
        "raw_material_idr": 42000,
        "processing_idr": 5000,
        "packaging_idr": 2500,
        "documentation_idr": 3500,
        "port_handling_idr": 2000,
        "margin_percent": 20
    },
    "Cassia Powder": {
        "hs_code": "0906.20",
        "origin": "Kerinci, Indonesia",
        "raw_material_idr": 42000,
        "processing_idr": 12000,
        "packaging_idr": 6000,
        "documentation_idr": 3500,
        "port_handling_idr": 2000,
        "margin_percent": 25
    },
    "Clove": {
        "hs_code": "0907.10",
        "origin": "North Maluku, Indonesia",
        "raw_material_idr": 95000,
        "processing_idr": 7000,
        "packaging_idr": 2500,
        "documentation_idr": 3500,
        "port_handling_idr": 2000,
        "margin_percent": 20
    },
    "Nutmeg": {
        "hs_code": "0908.11",
        "origin": "North Maluku, Indonesia",
        "raw_material_idr": 110000,
        "processing_idr": 7000,
        "packaging_idr": 2500,
        "documentation_idr": 3500,
        "port_handling_idr": 2000,
        "margin_percent": 20
    },
    "Vanilla": {
        "hs_code": "0905.10",
        "origin": "Papua, Indonesia",
        "raw_material_idr": 750000,
        "processing_idr": 25000,
        "packaging_idr": 35000,
        "documentation_idr": 5000,
        "port_handling_idr": 3000,
        "margin_percent": 25
    },
    "Patchouli Oil": {
        "hs_code": "3301.29",
        "origin": "Aceh, Indonesia",
        "raw_material_idr": 850000,
        "processing_idr": 30000,
        "packaging_idr": 85000,
        "documentation_idr": 5000,
        "port_handling_idr": 3000,
        "margin_percent": 25
    }
}

# ==============================================================================
# DOMESTIC FREIGHT TO EXPORT PORT
# ==============================================================================
DOMESTIC_FREIGHT_COST_IDR = {
    "Belawan Port": 3500,
    "Tanjung Priok Port": 4500,
    "Tanjung Perak Port": 5000,
    "Makassar Port": 5500
}

# ==============================================================================
# PACKAGING MASTER
# ==============================================================================
PACKAGING_TARE_WEIGHT = {
    "PP Woven Bag 25 Kg": {"tare": 0.30, "capacity": 25},
    "PP Woven Bag 50 Kg": {"tare": 0.35, "capacity": 50},
    "Kraft Paper Bag 20 Kg": {"tare": 0.25, "capacity": 20},
    "Kraft Paper Bag 25 Kg": {"tare": 0.30, "capacity": 25},
    "Vacuum Bag + Carton 5 Kg": {"tare": 0.50, "capacity": 5},
    "Vacuum Bag + Carton 10 Kg": {"tare": 0.80, "capacity": 10},
    "HDPE Drum 25 Kg": {"tare": 1.80, "capacity": 25},
    "Steel Drum 180 Kg": {"tare": 18.00, "capacity": 180},
    "Standard Bag": {"tare": 0.30, "capacity": 25}
}

# ==============================================================================
# FOB CALCULATOR
# ==============================================================================
def calculate_fob_price(commodity_name, volume_kg, packaging_type, loading_port, exchange_rate=16500):
    if commodity_name not in COMMODITY_FOB_MASTER:
        return {"error": f"Commodity '{commodity_name}' not found."}

    if loading_port not in DOMESTIC_FREIGHT_COST_IDR:
        return {"error": f"Port '{loading_port}' not found."}

    if volume_kg <= 0:
        return {"error": "Volume must be greater than zero."}

    data = COMMODITY_FOB_MASTER[commodity_name]
    margin_percent = data["margin_percent"]

    if margin_percent >= 100:
        return {"error": "Margin percentage must be below 100."}

    freight_idr = DOMESTIC_FREIGHT_COST_IDR[loading_port]

    raw_material_idr = data["raw_material_idr"]
    processing_idr = data["processing_idr"]
    packaging_idr = data["packaging_idr"]
    documentation_idr = data["documentation_idr"]
    port_handling_idr = data["port_handling_idr"]

    total_cost_per_kg_idr = (
        raw_material_idr +
        processing_idr +
        packaging_idr +
        freight_idr +
        documentation_idr +
        port_handling_idr
    )

    total_cost_per_kg_usd = total_cost_per_kg_idr / exchange_rate
    margin_decimal = margin_percent / 100
    fob_price_per_kg = total_cost_per_kg_usd / (1 - margin_decimal)

    total_cost_usd = total_cost_per_kg_usd * volume_kg
    fob_total_usd = fob_price_per_kg * volume_kg
    profit_usd = fob_total_usd - total_cost_usd

    pack_info = PACKAGING_TARE_WEIGHT.get(packaging_type, {"tare": 0.30, "capacity": 25})
    tare_per_unit = pack_info["tare"]
    pack_capacity = pack_info["capacity"]

    total_units_needed = math.ceil(volume_kg / pack_capacity)
    gross_weight_kg = volume_kg + (total_units_needed * tare_per_unit)

    # Perhatikan: Bagian return di bawah ini sekarang teridentasi masuk ke dalam fungsi
    return {
        "commodity": commodity_name,
        "hs_code": data["hs_code"],
        "origin": data["origin"],
        "loading_port": loading_port,
        "volume_kg": volume_kg,
        "net_weight_kg": volume_kg,
        "gross_weight_kg": round(gross_weight_kg, 2),
        "total_units_needed": total_units_needed,
        "exchange_rate": exchange_rate,
        "margin_percent": margin_percent,
        "total_cost_per_kg_idr": round(total_cost_per_kg_idr, 2),
        "total_cost_per_kg_usd": round(total_cost_per_kg_usd, 4),
        "fob_price_per_kg": round(fob_price_per_kg, 4),
        "fob_total_usd": round(fob_total_usd, 2),
        "total_cost_usd": round(total_cost_usd, 2),
        "profit_usd": round(profit_usd, 2),
        "breakdown_per_kg": {
            "raw_material_idr": raw_material_idr,
            "processing_idr": processing_idr,
            "packaging_idr": packaging_idr,
            "freight_idr": freight_idr,
            "documentation_idr": documentation_idr,
            "port_handling_idr": port_handling_idr
        },
        "breakdown_total": {
            "raw_material_idr": raw_material_idr * volume_kg,
            "processing_idr": processing_idr * volume_kg,
            "packaging_idr": packaging_idr * volume_kg,
            "freight_idr": freight_idr * volume_kg,
            "documentation_idr": documentation_idr * volume_kg,
            "port_handling_idr": port_handling_idr * volume_kg
        }
    }